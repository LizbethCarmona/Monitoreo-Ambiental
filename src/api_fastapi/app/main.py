"""API REST del proyecto Monitoreo ambiental en tiempo real.

Implementa la clase `APIServiceFastAPI` del UML (ver
docs/uml/diagrama_clases.puml) consultando MySQL (src/database/schema.sql):
getEstadoClima() y getAlertas() leen las tablas
`lecturas`, `alertas`, `sensores` y `umbrales` que el núcleo concurrente en
C++ (src/cpp_ingestion) va llenando con lecturas simuladas. La persistencia es
real; también puede recibir mensajes de sensores externos por MQTT cuando el suscriptor
se habilita. La ejecución demostrativa incluye un simulador, no mediciones físicas propias.

También sirve el dashboard estático (src/dashboard) en la misma app para
evitar problemas de CORS.
"""
import asyncio
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.concurrency import run_in_threadpool
from mysql.connector import Error as MySQLError

from . import db
from . import auth
from .ingestion import IngestorMQTT

_LOGGER = logging.getLogger(__name__)
_INTERVALO_WS_SEGUNDOS = float(os.getenv("WS_INTERVAL_SECONDS", "2"))
_ingestor_mqtt = IngestorMQTT()


class HubDashboard:
    def __init__(self) -> None:
        self.conexiones: set[WebSocket] = set()
        self.ultima_actualizacion: dict | None = None

    async def publicar(self, mensaje: dict) -> None:
        desconectados = []
        for conexion in tuple(self.conexiones):
            try:
                await conexion.send_json(mensaje)
            except (WebSocketDisconnect, RuntimeError):
                desconectados.append(conexion)
        for conexion in desconectados:
            self.conexiones.discard(conexion)

    async def ejecutar(self) -> None:
        while True:
            if self.conexiones:
                try:
                    estado, alertas = await run_in_threadpool(_crear_actualizacion)
                    self.ultima_actualizacion = {
                        "tipo": "actualizacion",
                        "estado": estado,
                        "alertas": alertas,
                    }
                    await self.publicar(self.ultima_actualizacion)
                except HTTPException as exc:
                    _LOGGER.warning("No se pudo publicar el estado WebSocket: %s", exc.detail)
                    await self.publicar({"tipo": "error", "mensaje": exc.detail})
                except MySQLError:
                    _LOGGER.exception("Fallo la consulta MySQL para el dashboard WebSocket.")
                    await self.publicar(
                        {"tipo": "error", "mensaje": "No se pudo consultar MySQL para el dashboard."}
                    )
            await asyncio.sleep(_INTERVALO_WS_SEGUNDOS)


_hub_dashboard = HubDashboard()


def _crear_actualizacion() -> tuple[dict, dict]:
    return get_estado_clima(), get_alertas()


@asynccontextmanager
async def _lifespan(_: FastAPI):
    auth.validar_configuracion()
    tarea_dashboard = asyncio.create_task(_hub_dashboard.ejecutar())
    mqtt_habilitado = os.getenv("MQTT_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
    if mqtt_habilitado:
        _ingestor_mqtt.iniciar()
    try:
        yield
    finally:
        tarea_dashboard.cancel()
        try:
            await tarea_dashboard
        except asyncio.CancelledError:
            pass
        _ingestor_mqtt.detener()


app = FastAPI(
    title="Monitoreo Ambiental en Tiempo Real - API",
    description=(
        "Expone en MySQL lecturas simuladas o recibidas por MQTT, sus agregados y alertas. "
        "No consulta fuentes meteorologicas."
    ),
    version="0.2.0",
    lifespan=_lifespan,
)

_LOGIN_DIR = Path(__file__).resolve().parents[2] / "dashboard"
_login_limitador = auth.LimitadorAccesos()


def _ruta_publica(path: str) -> bool:
    return path in {"/login", "/auth/login", "/auth/logout", "/healthz"} or path in {
        "/dashboard/login.css",
        "/dashboard/login.js",
    }


@app.middleware("http")
async def autenticar_solicitudes(request: Request, call_next):
    if not auth.enabled() or _ruta_publica(request.url.path):
        return await call_next(request)

    usuarios = auth.cargar_usuarios()
    usuario = request.session.get("usuario")
    if (
        not usuario
        or usuario not in usuarios
        or not auth.sesion_vigente(request.session)
    ):
        request.session.clear()
        if request.url.path == "/" or request.url.path.startswith("/dashboard"):
            return RedirectResponse("/login", status_code=303)
        return JSONResponse(
            {"detail": "Autenticación requerida."},
            status_code=401,
            headers={"Cache-Control": "no-store"},
        )
    return await call_next(request)


@app.get("/login", include_in_schema=False)
async def pagina_login() -> Response:
    if not auth.enabled():
        return RedirectResponse("/dashboard/", status_code=303)
    return FileResponse(_LOGIN_DIR / "login.html", headers={"Cache-Control": "no-store"})


@app.post("/auth/login", include_in_schema=False)
async def iniciar_sesion(request: Request) -> Response:
    if not auth.enabled():
        return JSONResponse({"detail": "El inicio de sesión no está habilitado."}, status_code=404)
    cliente = request.client.host if request.client else "unknown"
    espera = _login_limitador.esperar(cliente)
    if espera:
        return JSONResponse(
            {"detail": "Demasiados intentos. Espera un minuto antes de volver a intentarlo."},
            status_code=429,
            headers={"Retry-After": str(espera), "Cache-Control": "no-store"},
        )
    try:
        datos = await request.json()
    except (ValueError, UnicodeDecodeError):
        datos = {}
    usuario = datos.get("usuario", "") if isinstance(datos, dict) else ""
    contrasena = datos.get("contrasena", "") if isinstance(datos, dict) else ""
    if not isinstance(usuario, str) or not isinstance(contrasena, str):
        usuario = contrasena = ""
    hash_guardado = auth.cargar_usuarios().get(usuario)
    if not auth.verificar_contrasena(contrasena, hash_guardado or "") or hash_guardado is None:
        return JSONResponse(
            {"detail": "Usuario o contraseña incorrectos."},
            status_code=401,
            headers={"Cache-Control": "no-store"},
        )
    request.session.clear()
    request.session["usuario"] = usuario
    request.session["emitida"] = int(time.time())
    return JSONResponse({"autenticado": True}, headers={"Cache-Control": "no-store"})


@app.post("/auth/logout", include_in_schema=False)
async def cerrar_sesion(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict:
    return {"estado": "ok"}


CIUDAD_NOMBRE = os.getenv("CIUDAD_NOMBRE", "Ciudad de Mexico")

_DIAS = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
_MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

_ETIQUETA_NIVEL = {"normal": "Normal", "advertencia": "Advertencia", "critico": "Critico"}
_UNIDAD_METRICA = {"pm25": "\u00b5g/m\u00b3", "co2": "ppm", "tmp": "\u00b0C"}
_TITULO_METRICA = {"pm25": "PM2.5", "co2": "CO2", "tmp": "Temperatura"}


def _fecha_es(dt: datetime) -> str:
    return f"{_DIAS[dt.weekday()]}, {dt.day} {_MESES[dt.month - 1]}"


def _hora_label(dt: datetime) -> str:
    etiqueta = dt.strftime("%I %p").lstrip("0")
    return etiqueta if etiqueta else "12 AM"


def _cargar_umbrales(cursor) -> dict:
    cursor.execute("SELECT metrica, nivel, aplica_a, valor_limite FROM umbrales")
    umbrales = {}
    for metrica, nivel, aplica_a, valor_limite in cursor.fetchall():
        umbrales[(metrica, nivel, aplica_a)] = float(valor_limite)
    return umbrales


def _nivel_de(umbrales: dict, metrica: str, valor, aplica_a: str = "lectura") -> str:
    if valor is None:
        return "normal"
    valor = float(valor)
    if valor >= umbrales.get((metrica, "critico", aplica_a), float("inf")):
        return "critico"
    if valor >= umbrales.get((metrica, "advertencia", aplica_a), float("inf")):
        return "advertencia"
    return "normal"


@app.get("/estado-clima", summary="Equivalente a APIServiceFastAPI.getEstadoClima()")
def get_estado_clima() -> dict:
    try:
        conn = db.conectar()
    except (MySQLError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=f"No se pudo conectar a MySQL: {exc}") from exc

    try:
        cursor = conn.cursor()
        umbrales = _cargar_umbrales(cursor)

        cursor.execute("SELECT COUNT(*) FROM sensores WHERE activo = 1")
        (sensores_activos,) = cursor.fetchone()

        cursor.execute(
            "SELECT sensor_id, pm25, co2, tmp, timestamp_lectura FROM lecturas "
            "ORDER BY timestamp_lectura DESC LIMIT 1"
        )
        ultima = cursor.fetchone()

        cursor.execute(
            "SELECT MIN(tmp), MAX(tmp) FROM lecturas "
            "WHERE timestamp_lectura >= UTC_DATE() "
            "AND timestamp_lectura < UTC_DATE() + INTERVAL 1 DAY"
        )
        temp_min, temp_max = cursor.fetchone()

        cursor.execute(
            "SELECT AVG(pm25) FROM lecturas WHERE timestamp_lectura >= UTC_TIMESTAMP() - INTERVAL 24 HOUR"
        )
        (pm25_prom_24h,) = cursor.fetchone()

        cursor.execute(
            "SELECT AVG(co2) FROM lecturas WHERE timestamp_lectura >= UTC_TIMESTAMP() - INTERVAL 8 HOUR"
        )
        (co2_prom_8h,) = cursor.fetchone()

        cursor.execute(
            "SELECT DATE_FORMAT(timestamp_lectura, '%Y-%m-%d %H:00:00') AS hora_bucket, "
            "AVG(tmp) AS temp_prom, AVG(pm25) AS pm25_prom "
            "FROM lecturas WHERE timestamp_lectura >= UTC_TIMESTAMP() - INTERVAL 24 HOUR "
            "GROUP BY hora_bucket ORDER BY hora_bucket DESC LIMIT 24"
        )
        filas_hora = list(cursor.fetchall())[::-1]  # orden ascendente para mostrar de izq. a der.
    finally:
        conn.close()

    if ultima:
        sensor_ultima_lectura, pm25_actual, co2_actual, tmp_actual, ts_ultima_lectura = ultima
        hora_ultima_lectura = ts_ultima_lectura.strftime("%H:%M:%S UTC")
    else:
        sensor_ultima_lectura = None
        hora_ultima_lectura = None
        pm25_actual = co2_actual = tmp_actual = None

    pm25_nivel = _nivel_de(umbrales, "pm25", pm25_actual)
    co2_nivel = _nivel_de(umbrales, "co2", co2_actual)
    historial_horario = []
    for i, (hora_bucket, temp_prom, pm25_prom) in enumerate(filas_hora):
        dt = hora_bucket if isinstance(hora_bucket, datetime) else datetime.strptime(hora_bucket, "%Y-%m-%d %H:%M:%S")
        historial_horario.append(
            {
                "hora": _hora_label(dt),
                "fecha": f"{dt.day} {_MESES[dt.month - 1]}",
                "temp": round(float(temp_prom), 1) if temp_prom is not None else None,
                "pm25": round(float(pm25_prom), 1) if pm25_prom is not None else None,
                "nivel": _nivel_de(umbrales, "pm25", pm25_prom) if pm25_prom is not None else None,
                "actual": i == len(filas_hora) - 1,
            }
        )

    ahora = datetime.now(timezone.utc)
    return {
        "ciudad": CIUDAD_NOMBRE,
        "fecha": _fecha_es(ahora),
        "sensores_activos": sensores_activos,
        "sensor_ultima_lectura": sensor_ultima_lectura,
        "hora_ultima_lectura_utc": hora_ultima_lectura,
        "temperatura_actual": round(float(tmp_actual), 1) if tmp_actual is not None else None,
        "temperatura_min": round(float(temp_min), 1) if temp_min is not None else None,
        "temperatura_max": round(float(temp_max), 1) if temp_max is not None else None,
        "calidad_aire": _ETIQUETA_NIVEL[pm25_nivel],
        "calidad_aire_nivel": pm25_nivel,
        "pm2_5": round(float(pm25_actual), 1) if pm25_actual is not None else None,
        "pm2_5_nivel": pm25_nivel,
        "co2": round(float(co2_actual)) if co2_actual is not None else None,
        "co2_nivel": co2_nivel,
        "pm2_5_promedio_24h": round(float(pm25_prom_24h), 1) if pm25_prom_24h is not None else None,
        "pm2_5_promedio_24h_nivel": _nivel_de(umbrales, "pm25", pm25_prom_24h, "promedio_24h"),
        "pm2_5_limite_24h": umbrales.get(("pm25", "critico", "promedio_24h")),
        "co2_promedio_8h": round(float(co2_prom_8h)) if co2_prom_8h is not None else None,
        "co2_promedio_8h_nivel": _nivel_de(umbrales, "co2", co2_prom_8h, "promedio_8h"),
        "co2_limite_8h_advertencia": umbrales.get(("co2", "advertencia", "promedio_8h")),
        "co2_limite_8h_critico": umbrales.get(("co2", "critico", "promedio_8h")),
        "historial_horario": historial_horario,
        "pronostico_horario": historial_horario,
        "actualizado": ahora.isoformat(),
    }


@app.get("/alertas", summary="Equivalente a APIServiceFastAPI.getAlertas()")
def get_alertas() -> dict:
    try:
        conn = db.conectar()
    except (MySQLError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=f"No se pudo conectar a MySQL: {exc}") from exc

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM alertas WHERE atendida = 0")
        (total_alertas,) = cursor.fetchone()
        cursor.execute(
            "SELECT sensor_id, metrica, nivel, valor_medido, valor_limite, timestamp_alerta FROM alertas "
            "WHERE atendida = 0 ORDER BY timestamp_alerta DESC LIMIT 20"
        )
        filas = cursor.fetchall()
    finally:
        conn.close()

    alertas = []
    for sensor_id, metrica, nivel, valor_medido, valor_limite, ts in filas:
        alertas.append(
            {
                "titulo": f"{_TITULO_METRICA.get(metrica, metrica)} - {sensor_id}",
                "hora": ts.strftime("%H:%M"),
                "nivel": nivel,
                "valor_medido": round(float(valor_medido), 1),
                "valor_limite": round(float(valor_limite), 1),
                "unidad": _UNIDAD_METRICA.get(metrica, ""),
            }
        )
    return {"total": total_alertas, "alertas": alertas}


@app.get("/alertas/historial", summary="Historial reciente de alertas")
def get_historial_alertas(limite: int = Query(default=100, ge=1, le=500)) -> dict:
    try:
        conn = db.conectar()
    except (MySQLError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=f"No se pudo conectar a MySQL: {exc}") from exc

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM alertas")
        (total,) = cursor.fetchone()
        cursor.execute(
            "SELECT sensor_id, metrica, nivel, valor_medido, valor_limite, timestamp_alerta, atendida "
            "FROM alertas ORDER BY timestamp_alerta DESC LIMIT %s",
            (limite,),
        )
        filas = cursor.fetchall()
    finally:
        conn.close()

    alertas = []
    for sensor_id, metrica, nivel, valor_medido, valor_limite, ts, atendida in filas:
        alertas.append(
            {
                "titulo": f"{_TITULO_METRICA.get(metrica, metrica)} - {sensor_id}",
                "hora": ts.strftime("%H:%M"),
                "nivel": nivel,
                "valor_medido": round(float(valor_medido), 1),
                "valor_limite": round(float(valor_limite), 1),
                "unidad": _UNIDAD_METRICA.get(metrica, ""),
                "estado": "Atendida" if atendida else "Activa",
            }
        )
    return {"total": total, "alertas": alertas}


@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket) -> None:
    vence_sesion = None
    if auth.enabled():
        usuario = websocket.session.get("usuario")
        emitida = websocket.session.get("emitida")
        if (
            not usuario
            or usuario not in auth.cargar_usuarios()
            or not auth.sesion_vigente(websocket.session)
        ):
            await websocket.close(code=1008)
            return
        origen = websocket.headers.get("origin")
        host = websocket.headers.get("host", "")
        if not origen or urlsplit(origen).netloc.lower() != host.lower():
            await websocket.close(code=1008)
            return
        vence_sesion = asyncio.get_running_loop().time() + max(
            0, auth.session_max_age() - (time.time() - emitida)
        )
    await websocket.accept()
    _hub_dashboard.conexiones.add(websocket)
    try:
        estado, alertas = await run_in_threadpool(_crear_actualizacion)
        _hub_dashboard.ultima_actualizacion = {
            "tipo": "actualizacion",
            "estado": estado,
            "alertas": alertas,
        }
        await websocket.send_json(_hub_dashboard.ultima_actualizacion)
        while True:
            try:
                mensaje = await asyncio.wait_for(websocket.receive_text(), timeout=20)
            except asyncio.TimeoutError:
                if vence_sesion is not None and asyncio.get_running_loop().time() >= vence_sesion:
                    await websocket.close(code=1008)
                    _hub_dashboard.conexiones.discard(websocket)
                    return
                continue
            if mensaje == "ping":
                await websocket.send_json({"tipo": "pong"})
    except WebSocketDisconnect:
        _hub_dashboard.conexiones.discard(websocket)
    except HTTPException as exc:
        _LOGGER.warning("No se pudo iniciar la sesion WebSocket: %s", exc.detail)
        await websocket.send_json({"tipo": "error", "mensaje": exc.detail})
        await websocket.close(code=1011)
        _hub_dashboard.conexiones.discard(websocket)
    except MySQLError:
        _LOGGER.exception("Fallo la consulta MySQL al abrir una sesion WebSocket.")
        await websocket.send_json(
            {"tipo": "error", "mensaje": "No se pudo consultar MySQL para el dashboard."}
        )
        await websocket.close(code=1011)
        _hub_dashboard.conexiones.discard(websocket)


@app.get("/salud", summary="Chequeo de disponibilidad de API, MySQL y MQTT")
def get_salud() -> dict:
    try:
        conn = db.conectar()
        conn.close()
        mqtt_estado = _ingestor_mqtt.estado
        mqtt_habilitado = os.getenv("MQTT_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
        return {
            "estado": "ok" if not mqtt_habilitado or mqtt_estado["estado"] == "conectado" else "degradado",
            "mysql": "conectado",
            "mqtt_habilitado": mqtt_habilitado,
            "mqtt": mqtt_estado,
        }
    except (MySQLError, RuntimeError) as exc:
        return {
            "estado": "degradado",
            "mysql": f"error: {exc}",
            "mqtt_habilitado": os.getenv("MQTT_ENABLED", "false").strip().lower() in {"1", "true", "yes"},
            "mqtt": _ingestor_mqtt.estado,
        }


# Sirve el dashboard estatico (src/dashboard) en la misma app para evitar
# problemas de CORS al hacer fetch() a /estado-clima y /alertas desde el
# navegador. Se monta al final para no tapar las rutas de la API de arriba.
_DASHBOARD_DIR = Path(__file__).resolve().parents[2] / "dashboard"
if _DASHBOARD_DIR.is_dir():
    app.mount("/dashboard", StaticFiles(directory=str(_DASHBOARD_DIR), html=True), name="dashboard")

_ALLOWED_HOSTS = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "").split(",") if host.strip()]
if _ALLOWED_HOSTS:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_ALLOWED_HOSTS)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("DASHBOARD_SESSION_SECRET") or secrets.token_urlsafe(48),
    session_cookie="monitoreo_session",
    max_age=auth.session_max_age(),
    same_site="strict",
    https_only=auth.cookie_secure(),
)
