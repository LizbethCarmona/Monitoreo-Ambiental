"""API REST del proyecto Monitoreo ambiental en tiempo real.

Implementa la clase `APIServiceFastAPI` del UML (ver
docs/uml/diagrama_clases.puml) consultando datos REALES de MySQL
(src/database/schema.sql): getEstadoClima() y getAlertas() leen las tablas
`lecturas`, `alertas`, `sensores` y `umbrales` que el núcleo concurrente en
C++ (src/cpp_ingestion) va llenando en tiempo real.

También sirve el dashboard estático (src/dashboard) en la misma app para
evitar problemas de CORS.
"""
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from mysql.connector import Error as MySQLError

from . import db

app = FastAPI(
    title="Monitoreo Ambiental en Tiempo Real - API",
    description="Expone el estado del clima/calidad del aire y las alertas activas (datos reales de MySQL).",
    version="0.2.0",
)

CIUDAD_NOMBRE = "Ciudad de Mexico"  # el esquema no guarda ciudad; TODO: agregarla a `sensores` si se vuelve multi-ciudad.

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
    # Simplificacion: igual que include/Umbrales.hpp en el nucleo de C++, se
    # trata cada umbral como si aplicara a la lectura puntual (el esquema
    # real distingue 'lectura' / 'promedio_8h' / 'promedio_24h' en la
    # columna aplica_a; ver src/database/schema.sql para el detalle normado).
    cursor.execute("SELECT metrica, nivel, valor_limite FROM umbrales")
    umbrales: dict = {}
    for metrica, nivel, valor_limite in cursor.fetchall():
        umbrales.setdefault((metrica, nivel), float(valor_limite))
    return umbrales


def _nivel_de(umbrales: dict, metrica: str, valor) -> str:
    if valor is None:
        return "normal"
    valor = float(valor)
    if valor >= umbrales.get((metrica, "critico"), float("inf")):
        return "critico"
    if valor >= umbrales.get((metrica, "advertencia"), float("inf")):
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
            "WHERE timestamp_lectura >= UTC_TIMESTAMP() - INTERVAL 24 HOUR"
        )
        temp_min, temp_max = cursor.fetchone()

        cursor.execute(
            "SELECT AVG(pm25) FROM lecturas WHERE timestamp_lectura >= UTC_TIMESTAMP() - INTERVAL 24 HOUR"
        )
        (pm25_prom_24h,) = cursor.fetchone()

        cursor.execute(
            "SELECT DATE_FORMAT(timestamp_lectura, '%Y-%m-%d %H:00:00') AS hora_bucket, "
            "AVG(tmp) AS temp_prom, AVG(pm25) AS pm25_prom "
            "FROM lecturas GROUP BY hora_bucket ORDER BY hora_bucket DESC LIMIT 10"
        )
        filas_hora = list(cursor.fetchall())[::-1]  # orden ascendente para mostrar de izq. a der.
    finally:
        conn.close()

    if ultima:
        _, pm25_actual, co2_actual, tmp_actual, _ts = ultima
    else:
        pm25_actual = co2_actual = tmp_actual = None

    pm25_nivel = _nivel_de(umbrales, "pm25", pm25_actual)
    co2_nivel = _nivel_de(umbrales, "co2", co2_actual)
    tmp_nivel = pm25_nivel  # la calidad del aire mostrada se basa en PM2.5, igual que el badge principal

    pronostico_horario = []
    for i, (hora_bucket, temp_prom, pm25_prom) in enumerate(filas_hora):
        dt = hora_bucket if isinstance(hora_bucket, datetime) else datetime.strptime(hora_bucket, "%Y-%m-%d %H:%M:%S")
        pronostico_horario.append(
            {
                "hora": _hora_label(dt),
                "temp": round(float(temp_prom), 1) if temp_prom is not None else 0,
                "nivel": _nivel_de(umbrales, "pm25", pm25_prom),
                "actual": i == len(filas_hora) - 1,
            }
        )

    ahora = datetime.now(timezone.utc)
    return {
        "ciudad": CIUDAD_NOMBRE,
        "fecha": _fecha_es(ahora),
        "sensores_activos": sensores_activos,
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
        "pm2_5_promedio_24h_nivel": "critico" if (pm25_prom_24h or 0) >= umbrales.get(("pm25", "critico"), 41.0) else "normal",
        "pm2_5_limite_24h": umbrales.get(("pm25", "critico"), 41.0),
        "pronostico_horario": pronostico_horario,
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
    return {"total": len(alertas), "alertas": alertas}


@app.get("/salud", summary="Chequeo simple de disponibilidad del servicio (API + MySQL)")
def get_salud() -> dict:
    try:
        conn = db.conectar()
        conn.close()
        return {"estado": "ok", "mysql": "conectado"}
    except (MySQLError, RuntimeError) as exc:
        return {"estado": "degradado", "mysql": f"error: {exc}"}


# Sirve el dashboard estatico (src/dashboard) en la misma app para evitar
# problemas de CORS al hacer fetch() a /estado-clima y /alertas desde el
# navegador. Se monta al final para no tapar las rutas de la API de arriba.
_DASHBOARD_DIR = Path(__file__).resolve().parents[2] / "dashboard"
if _DASHBOARD_DIR.is_dir():
    app.mount("/dashboard", StaticFiles(directory=str(_DASHBOARD_DIR), html=True), name="dashboard")
