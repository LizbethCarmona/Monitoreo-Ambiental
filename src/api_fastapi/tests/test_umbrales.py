import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from mysql.connector import Error as MySQLError

from app.ingestion import (
    LecturaValidada,
    elegir_alerta,
    persistir_lectura_mqtt,
    validar_mensaje_mqtt,
)
from app.main import _cargar_umbrales, _nivel_de, get_estado_clima, get_historial_alertas
from app.main import app


class CursorDePrueba:
    def __init__(self):
        self.consulta = None

    def execute(self, consulta):
        self.consulta = consulta

    def fetchall(self):
        return [
            ("pm25", "advertencia", "lectura", 35.0),
            ("pm25", "critico", "lectura", 75.0),
            ("pm25", "critico", "promedio_24h", 25.0),
            ("co2", "advertencia", "promedio_8h", 2500.0),
            ("co2", "critico", "promedio_8h", 5000.0),
            ("co2", "critico", "lectura", 30000.0),
        ]


class CursorHistorialDePrueba:
    def __init__(self):
        self.resultado = None
        self.parametros = None

    def execute(self, consulta, parametros=None):
        self.parametros = parametros
        self.resultado = 27 if "COUNT(*)" in consulta else [
            ("sensor_01", "pm25", "critico", 82.5, 75.0, datetime(2026, 10, 14, 18, 49), False)
        ]

    def fetchone(self):
        return (self.resultado,)

    def fetchall(self):
        return self.resultado


class CursorEstadoClimaDePrueba:
    def __init__(self):
        self.tipo_consulta = None
        self.consulta_horaria = None

    def execute(self, consulta):
        if consulta.startswith("SELECT metrica"):
            self.tipo_consulta = "umbrales"
        elif "COUNT(*) FROM sensores" in consulta:
            self.tipo_consulta = "sensores"
        elif "SELECT sensor_id, pm25" in consulta:
            self.tipo_consulta = "ultima"
        elif "MIN(tmp)" in consulta:
            self.tipo_consulta = "temperatura_dia"
        elif "DATE_FORMAT(timestamp_lectura" in consulta:
            self.tipo_consulta = "horas"
            self.consulta_horaria = consulta
        elif "AVG(pm25)" in consulta:
            self.tipo_consulta = "pm25_24h"
        elif "AVG(co2)" in consulta:
            self.tipo_consulta = "co2_8h"
        else:
            raise AssertionError(f"Consulta no esperada: {consulta}")

    def fetchone(self):
        resultados = {
            "sensores": (3,),
            "ultima": ("sensor_01", 22.5, 650, 24.0, datetime(2026, 10, 15, 19, 30)),
            "temperatura_dia": (20.0, 28.0),
            "pm25_24h": (21.0,),
            "co2_8h": (700.0,),
        }
        return resultados[self.tipo_consulta]

    def fetchall(self):
        if self.tipo_consulta == "umbrales":
            return [
                ("pm25", "advertencia", "lectura", 35.0),
                ("pm25", "critico", "lectura", 75.0),
                ("pm25", "critico", "promedio_24h", 25.0),
                ("co2", "advertencia", "promedio_8h", 2500.0),
                ("co2", "critico", "promedio_8h", 5000.0),
            ]
        if self.tipo_consulta == "horas":
            return [
                ("2026-10-15 19:00:00", 24.0, 36.0),
                ("2026-10-15 18:00:00", 23.0, 24.5),
            ]
        raise AssertionError(f"No se esperaba fetchall para {self.tipo_consulta}")


class ConexionEstadoClimaDePrueba:
    def __init__(self):
        self.cursor_de_prueba = CursorEstadoClimaDePrueba()
        self.cerrada = False

    def cursor(self):
        return self.cursor_de_prueba

    def close(self):
        self.cerrada = True


class CursorPersistenciaDePrueba:
    lastrowid = 42

    def __init__(self, duplicada=False):
        self.consultas = []
        self.duplicada = duplicada

    def execute(self, consulta, parametros=None):
        self.consultas.append((consulta, parametros))
        if self.duplicada and consulta.startswith("INSERT INTO lecturas"):
            raise MySQLError("duplicada", errno=1062)

    def fetchall(self):
        return [
            ("pm25", "advertencia", 35),
            ("pm25", "critico", 75),
            ("co2", "critico", 30000),
            ("tmp", "advertencia", 30),
            ("tmp", "critico", 32.2),
        ]


class ConexionPersistenciaDePrueba:
    def __init__(self, duplicada=False):
        self.cursor_de_prueba = CursorPersistenciaDePrueba(duplicada)
        self.commit_count = 0
        self.rollback_count = 0
        self.cerrada = False

    def cursor(self):
        return self.cursor_de_prueba

    def start_transaction(self):
        pass

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1

    def close(self):
        self.cerrada = True


class ConexionHistorialDePrueba:
    def __init__(self):
        self.cursor_de_prueba = CursorHistorialDePrueba()
        self.cerrada = False

    def cursor(self):
        return self.cursor_de_prueba

    def close(self):
        self.cerrada = True


class PruebasUmbrales(unittest.TestCase):
    def test_carga_y_separa_aplicabilidad(self):
        cursor = CursorDePrueba()
        umbrales = _cargar_umbrales(cursor)

        self.assertIn("aplica_a", cursor.consulta)
        self.assertEqual(_nivel_de(umbrales, "pm25", 50, "lectura"), "advertencia")
        self.assertEqual(_nivel_de(umbrales, "pm25", 24.99, "promedio_24h"), "normal")
        self.assertEqual(_nivel_de(umbrales, "pm25", 25.0, "promedio_24h"), "critico")
        self.assertEqual(_nivel_de(umbrales, "pm25", 50, "promedio_24h"), "critico")
        self.assertEqual(_nivel_de(umbrales, "co2", 3000, "lectura"), "normal")
        self.assertEqual(_nivel_de(umbrales, "co2", 3000, "promedio_8h"), "advertencia")

    def test_valor_ausente_no_produce_alerta(self):
        self.assertEqual(_nivel_de({}, "pm25", None), "normal")

    def test_estado_clima_expone_promedios_horarios_con_fecha_y_clasificacion(self):
        conexion = ConexionEstadoClimaDePrueba()
        with patch("app.main.db.conectar", return_value=conexion):
            respuesta = get_estado_clima()

        self.assertEqual(
            respuesta["historial_horario"],
            [
                {
                    "hora": "6 PM",
                    "fecha": "15 oct",
                    "temp": 23.0,
                    "pm25": 24.5,
                    "nivel": "normal",
                    "actual": False,
                },
                {
                    "hora": "7 PM",
                    "fecha": "15 oct",
                    "temp": 24.0,
                    "pm25": 36.0,
                    "nivel": "advertencia",
                    "actual": True,
                },
            ],
        )
        self.assertIn("LIMIT 24", conexion.cursor_de_prueba.consulta_horaria)
        self.assertTrue(conexion.cerrada)

    def test_historial_responde_con_total_y_limite_solicitado(self):
        conexion = ConexionHistorialDePrueba()
        with patch("app.main.db.conectar", return_value=conexion):
            respuesta = get_historial_alertas(5)

        self.assertEqual(respuesta["total"], 27)
        self.assertEqual(len(respuesta["alertas"]), 1)
        self.assertEqual(respuesta["alertas"][0]["estado"], "Activa")
        self.assertEqual(respuesta["alertas"][0]["titulo"], "PM2.5 - sensor_01")
        self.assertEqual(conexion.cursor_de_prueba.parametros, (5,))
        self.assertTrue(conexion.cerrada)

    def test_websocket_entrega_estado_y_alertas_iniciales(self):
        estado = {"temperatura_actual": 23.5}
        alertas = {"total": 0, "alertas": []}
        with TestClient(app) as cliente, patch("app.main._crear_actualizacion", return_value=(estado, alertas)):
            with cliente.websocket_connect("/ws/dashboard") as websocket:
                mensaje = websocket.receive_json()
                websocket.send_text("ping")
                latido = websocket.receive_json()

        self.assertEqual(mensaje, {"tipo": "actualizacion", "estado": estado, "alertas": alertas})
        self.assertEqual(latido, {"tipo": "pong"})

    def test_websocket_difunde_a_dos_clientes_simultaneos(self):
        estado = {"temperatura_actual": 23.5}
        alertas = {"total": 1, "alertas": [{"titulo": "PM2.5"}]}
        actualizacion = {"tipo": "actualizacion", "estado": estado, "alertas": alertas}
        with (
            TestClient(app) as cliente,
            patch("app.main._crear_actualizacion", return_value=(estado, alertas)),
            patch("app.main._INTERVALO_WS_SEGUNDOS", 0.01),
        ):
            with cliente.websocket_connect("/ws/dashboard") as primero:
                with cliente.websocket_connect("/ws/dashboard") as segundo:
                    primero.receive_json()
                    segundo.receive_json()
                    mensaje_primero = primero.receive_json()
                    mensaje_segundo = segundo.receive_json()

        self.assertEqual(mensaje_primero, actualizacion)
        self.assertEqual(mensaje_segundo, actualizacion)

    def test_salud_identifica_mqtt_deshabilitado(self):
        conexion = Mock()
        with (
            TestClient(app) as cliente,
            patch("app.main.db.conectar", return_value=conexion),
            patch.dict("os.environ", {"MQTT_ENABLED": "false"}),
        ):
            respuesta = cliente.get("/salud")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["estado"], "ok")
        self.assertFalse(respuesta.json()["mqtt_habilitado"])
        self.assertNotIn("password", str(respuesta.json()).lower())


class PruebasIngestionMQTT(unittest.TestCase):
    def test_valida_lectura_y_normaliza_timestamp_a_utc(self):
        payload = (
            b'{"sensor_id":"sensor_01","pm2.5":42.5,"co2":800,"tmp":24.1,'
            b'"timestamp":"2026-10-13T18:00:00-06:00"}'
        )
        lectura = validar_mensaje_mqtt("monitoreo/lecturas/sensor_01", payload)
        self.assertEqual(lectura.timestamp, datetime(2026, 10, 14, 0, 0, tzinfo=timezone.utc))

    def test_rechaza_topic_malformado_y_timestamp_sin_zona(self):
        payload = (
            b'{"sensor_id":"sensor_01","pm2.5":10,"co2":800,"tmp":24.1,'
            b'"timestamp":"2026-10-13T18:00:00"}'
        )
        with self.assertRaises(ValueError):
            validar_mensaje_mqtt("otro/sensor_01", payload)
        with self.assertRaises(ValueError):
            validar_mensaje_mqtt("monitoreo/lecturas/sensor_01", payload)

    def test_prioriza_alerta_critica_sobre_advertencias(self):
        lectura = LecturaValidada("sensor_01", 80, 6000, 33, datetime.now().astimezone())
        umbrales = {
            ("pm25", "critico", "lectura"): 75,
            ("co2", "critico", "lectura"): 5000,
            ("tmp", "critico", "lectura"): 32.2,
            ("pm25", "advertencia", "lectura"): 35,
        }
        self.assertEqual(elegir_alerta(lectura, umbrales), ("pm25", "critico", 80, 75))

    def test_lectura_y_alerta_se_confirman_en_una_transaccion(self):
        conexion = ConexionPersistenciaDePrueba()
        lectura = LecturaValidada(
            "sensor_01", 82.5, 800, 22,
            datetime(2026, 10, 14, 0, 0, tzinfo=timezone.utc),
        )
        with patch("app.ingestion.db.conectar", return_value=conexion):
            resultado = persistir_lectura_mqtt(lectura)

        consultas = [consulta for consulta, _ in conexion.cursor_de_prueba.consultas]
        self.assertEqual(resultado, "guardada")
        self.assertEqual(conexion.commit_count, 1)
        self.assertEqual(conexion.rollback_count, 0)
        self.assertTrue(any(consulta.startswith("INSERT INTO lecturas") for consulta in consultas))
        self.assertTrue(any(consulta.startswith("INSERT INTO alertas") for consulta in consultas))
        self.assertTrue(conexion.cerrada)

    def test_lectura_duplicada_hace_rollback_sin_alerta(self):
        conexion = ConexionPersistenciaDePrueba(duplicada=True)
        lectura = LecturaValidada(
            "sensor_01", 82.5, 800, 22,
            datetime(2026, 10, 14, 0, 0, tzinfo=timezone.utc),
        )
        with patch("app.ingestion.db.conectar", return_value=conexion):
            resultado = persistir_lectura_mqtt(lectura)

        consultas = [consulta for consulta, _ in conexion.cursor_de_prueba.consultas]
        self.assertEqual(resultado, "duplicada")
        self.assertEqual(conexion.commit_count, 0)
        self.assertEqual(conexion.rollback_count, 1)
        self.assertFalse(any(consulta.startswith("INSERT INTO alertas") for consulta in consultas))

    def test_no_confirma_mqtt_hasta_persistir(self):
        import json
        from app.ingestion import IngestorMQTT

        cliente = Mock()
        mensaje = Mock(
            topic="monitoreo/lecturas/sensor_01",
            payload=json.dumps(
                {
                    "sensor_id": "sensor_01",
                    "pm2.5": 10,
                    "co2": 500,
                    "tmp": 22,
                    "timestamp": "2026-10-13T18:00:00Z",
                }
            ).encode(),
            mid=17,
            qos=1,
        )
        ingestor = IngestorMQTT()
        with patch("app.ingestion.persistir_lectura_mqtt", side_effect=MySQLError("db off")):
            with self.assertLogs("app.ingestion", level="ERROR"):
                ingestor._al_mensaje(cliente, None, mensaje)
        cliente.ack.assert_not_called()
        self.assertEqual(ingestor.estado["estado"], "degradado")


if __name__ == "__main__":
    unittest.main()
