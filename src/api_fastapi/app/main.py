"""API REST del proyecto Monitoreo ambiental en tiempo real.

Esqueleto inicial (Sprint 1) para la clase `APIServiceFastAPI` del UML
(ver docs/uml/diagrama_clases.puml). La implementación completa —
conexión real a MySQL, motor de alertas y WebSockets— corresponde a los
Sprints 3 (Semanas 5-6) del cronograma.

Por ahora expone los mismos dos endpoints de solo lectura definidos en el
UML (getEstadoClima / getAlertas) devolviendo datos de ejemplo, y además
sirve el dashboard estático (src/dashboard) en la misma app para que el
equipo pueda ver la interfaz completa funcionando sin esperar a que la
capa de persistencia real esté conectada.
"""
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="Monitoreo Ambiental en Tiempo Real - API",
    description="Expone el estado del clima/calidad del aire y las alertas activas.",
    version="0.1.0",
)

# TODO (Sprint 3, Semana 5): reemplazar estos datos de ejemplo por consultas
# reales a MySQL (ver src/database/schema.sql) a través de un DatabaseManager
# equivalente al de C++, o conectando directamente con un driver async
# (por ejemplo aiomysql / SQLAlchemy async). Los umbrales (*_nivel) deben
# calcularse comparando contra la tabla `umbrales`, igual que
# ThreadPoolConsumidor::evaluarUmbrales en el núcleo concurrente de C++.
_ESTADO_CLIMA_EJEMPLO = {
    "ciudad": "Ciudad de Mexico",
    "fecha": "Jueves, 8 oct",
    "sensores_activos": 3,
    "temperatura_actual": 24.0,
    "temperatura_min": 12.0,
    "temperatura_max": 24.0,
    "calidad_aire": "Normal",
    "calidad_aire_nivel": "normal",
    "pm2_5": 18.0,
    "pm2_5_nivel": "normal",
    "co2": 420,
    "co2_nivel": "normal",
    "pm2_5_promedio_24h": 32.0,
    "pm2_5_promedio_24h_nivel": "normal",
    "pm2_5_limite_24h": 41,
    "pronostico_horario": [
        {"hora": "2 AM", "temp": 13, "nivel": "normal"},
        {"hora": "3 AM", "temp": 12, "nivel": "normal"},
        {"hora": "4 AM", "temp": 12, "nivel": "normal"},
        {"hora": "5 AM", "temp": 13, "nivel": "normal"},
        {"hora": "6 AM", "temp": 13, "nivel": "normal"},
        {"hora": "7 AM", "temp": 15, "nivel": "normal"},
        {"hora": "8 AM", "temp": 17, "nivel": "advertencia"},
        {"hora": "9 AM", "temp": 19, "nivel": "advertencia"},
        {"hora": "10 AM", "temp": 22, "nivel": "normal"},
        {"hora": "11 AM", "temp": 24, "nivel": "normal", "actual": True},
    ],
    "actualizado": None,
}

_ALERTAS_EJEMPLO = [
    {
        "titulo": "PM2.5 - sensor_03",
        "hora": "10:58",
        "nivel": "critico",
        "valor_medido": 85.0,
        "valor_limite": 75,
        "unidad": "µg/m³",
    },
    {
        "titulo": "PM2.5 - sensor_02",
        "hora": "10:45",
        "nivel": "advertencia",
        "valor_medido": 48.2,
        "valor_limite": 35,
        "unidad": "µg/m³",
    },
    {
        "titulo": "Temperatura - sensor_03",
        "hora": "10:31",
        "nivel": "advertencia",
        "valor_medido": 31.4,
        "valor_limite": 30.0,
        "unidad": "°C",
    },
    {
        "titulo": "PM2.5 prom. 24 h - sensor_03",
        "hora": "10:03",
        "nivel": "critico",
        "valor_medido": 43.1,
        "valor_limite": 41,
        "unidad": "µg/m³",
    },
]


@app.get("/estado-clima", summary="Equivalente a APIServiceFastAPI.getEstadoClima()")
def get_estado_clima() -> dict:
    datos = dict(_ESTADO_CLIMA_EJEMPLO)
    datos["actualizado"] = datetime.now(timezone.utc).isoformat()
    return datos


@app.get("/alertas", summary="Equivalente a APIServiceFastAPI.getAlertas()")
def get_alertas() -> dict:
    return {"total": len(_ALERTAS_EJEMPLO), "alertas": _ALERTAS_EJEMPLO}


@app.get("/salud", summary="Chequeo simple de disponibilidad del servicio")
def get_salud() -> dict:
    return {"estado": "ok"}


# Sirve el dashboard estatico (src/dashboard) en la misma app para evitar
# problemas de CORS al hacer fetch() a /estado-clima y /alertas desde el
# navegador. Se monta al final para no tapar las rutas de la API de arriba.
_DASHBOARD_DIR = Path(__file__).resolve().parents[2] / "dashboard"
if _DASHBOARD_DIR.is_dir():
    app.mount("/dashboard", StaticFiles(directory=str(_DASHBOARD_DIR), html=True), name="dashboard")
