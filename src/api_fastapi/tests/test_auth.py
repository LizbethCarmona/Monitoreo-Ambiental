import os
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import auth
from app.auth import crear_hash_contrasena, validar_hash, verificar_contrasena
from app.main import app


class PruebasAutenticacion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hash_valido = crear_hash_contrasena("UnaClaveDePruebaSegura123!")

    def configuracion(self):
        return {
            "APP_ENV": "development",
            "DASHBOARD_AUTH_ENABLED": "true",
            "DASHBOARD_SESSION_SECRET": "x" * 48,
            "DASHBOARD_USERS": f"sebas:{self.hash_valido}",
            "DASHBOARD_COOKIE_SECURE": "false",
            "DASHBOARD_SESSION_MAX_AGE": "3600",
            "ALLOWED_HOSTS": "",
        }

    def test_hash_pbkdf2_valida_contrasena_y_no_la_revela(self):
        self.assertTrue(validar_hash(self.hash_valido))
        self.assertTrue(verificar_contrasena("UnaClaveDePruebaSegura123!", self.hash_valido))
        self.assertFalse(verificar_contrasena("otra contraseña incorrecta", self.hash_valido))
        self.assertNotIn("UnaClaveDePruebaSegura123!", self.hash_valido)

    def test_sesion_expira_desde_el_momento_del_login(self):
        with patch.dict(os.environ, self.configuracion(), clear=False):
            self.assertTrue(auth.sesion_vigente({"emitida": 1000}, ahora=4599))
            self.assertFalse(auth.sesion_vigente({"emitida": 1000}, ahora=4600))
            self.assertFalse(auth.sesion_vigente({"emitida": "1000"}, ahora=1001))

    def test_produccion_exige_autenticacion_cookie_segura_y_host(self):
        configuracion = self.configuracion()
        configuracion.update(
            {
                "APP_ENV": "production",
                "DASHBOARD_COOKIE_SECURE": "true",
                "ALLOWED_HOSTS": "dashboard.example.test",
            }
        )
        with patch.dict(os.environ, configuracion, clear=False):
            auth.validar_configuracion()

        configuracion["DASHBOARD_COOKIE_SECURE"] = "false"
        with patch.dict(os.environ, configuracion, clear=False):
            with self.assertRaisesRegex(RuntimeError, "DASHBOARD_COOKIE_SECURE"):
                auth.validar_configuracion()

        configuracion["DASHBOARD_AUTH_ENABLED"] = "false"
        with patch.dict(os.environ, configuracion, clear=False):
            with self.assertRaisesRegex(RuntimeError, "DASHBOARD_AUTH_ENABLED"):
                auth.validar_configuracion()

    def test_rechaza_acceso_sin_sesion_y_redirige_dashboard_al_login(self):
        with patch.dict(os.environ, self.configuracion(), clear=False), TestClient(app) as cliente:
            respuesta_api = cliente.get("/estado-clima", headers={"Accept": "application/json"})
            respuesta_panel = cliente.get("/dashboard/", follow_redirects=False)
            respuesta_login = cliente.get("/login")

        self.assertEqual(respuesta_api.status_code, 401)
        self.assertEqual(respuesta_panel.status_code, 303)
        self.assertEqual(respuesta_panel.headers["location"], "/login")
        self.assertEqual(respuesta_login.status_code, 200)
        self.assertIn("Inicia sesión", respuesta_login.text)

    def test_login_sesion_y_logout_protegen_api(self):
        with (
            patch.dict(os.environ, self.configuracion(), clear=False),
            patch("app.main._login_limitador", auth.LimitadorAccesos()),
            patch("app.main.db.conectar", return_value=Mock()),
            TestClient(app) as cliente,
        ):
            invalido = cliente.post(
                "/auth/login",
                json={"usuario": "sebas", "contrasena": "incorrecta"},
            )
            login = cliente.post(
                "/auth/login",
                json={"usuario": "sebas", "contrasena": "UnaClaveDePruebaSegura123!"},
            )
            salud = cliente.get("/salud")
            logout = cliente.post("/auth/logout")
            sin_sesion = cliente.get("/alertas", headers={"Accept": "application/json"})

        self.assertEqual(invalido.status_code, 401)
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json(), {"autenticado": True})
        self.assertIn("httponly", login.headers["set-cookie"].lower())
        self.assertIn("samesite=strict", login.headers["set-cookie"].lower())
        self.assertEqual(salud.status_code, 200)
        self.assertEqual(logout.status_code, 204)
        self.assertEqual(sin_sesion.status_code, 401)

    def test_websocket_requiere_sesion_autenticada(self):
        with patch.dict(os.environ, self.configuracion(), clear=False), TestClient(app) as cliente:
            with self.assertRaises(WebSocketDisconnect):
                with cliente.websocket_connect("/ws/dashboard"):
                    pass

    def test_websocket_acepta_sesion_y_origen_del_mismo_host(self):
        with (
            patch.dict(os.environ, self.configuracion(), clear=False),
            patch("app.main._login_limitador", auth.LimitadorAccesos()),
            patch("app.main._crear_actualizacion", return_value=({"temperatura_actual": 22}, {"total": 0, "alertas": []})),
            TestClient(app) as cliente,
        ):
            login = cliente.post(
                "/auth/login",
                json={"usuario": "sebas", "contrasena": "UnaClaveDePruebaSegura123!"},
            )
            with cliente.websocket_connect(
                "/ws/dashboard",
                headers={"origin": "http://testserver"},
            ) as websocket:
                mensaje = websocket.receive_json()

        self.assertEqual(login.status_code, 200)
        self.assertEqual(mensaje["estado"]["temperatura_actual"], 22)

    def test_login_limita_intentos_por_direccion(self):
        with patch.dict(os.environ, self.configuracion(), clear=False), TestClient(app) as cliente:
            for _ in range(10):
                respuesta = cliente.post(
                    "/auth/login",
                    json={"usuario": "sebas", "contrasena": "incorrecta"},
                )
                self.assertEqual(respuesta.status_code, 401)
            limitada = cliente.post(
                "/auth/login",
                json={"usuario": "sebas", "contrasena": "UnaClaveDePruebaSegura123!"},
            )

        self.assertEqual(limitada.status_code, 429)
        self.assertIn("retry-after", limitada.headers)

    def test_limitador_limita_memoria_y_admite_clientes_al_vencer_ventana(self):
        limitador = auth.LimitadorAccesos(max_clientes=1, ventana_segundos=60)
        with patch("app.auth.time.monotonic", return_value=100):
            self.assertEqual(limitador.esperar("cliente-a"), 0)
            self.assertEqual(limitador.esperar("cliente-b"), 60)
        with patch("app.auth.time.monotonic", return_value=160):
            self.assertEqual(limitador.esperar("cliente-b"), 0)


if __name__ == "__main__":
    unittest.main()
