"""API REST del proyecto Monitoreo ambiental en tiempo real.

Esqueleto inicial (Sprint 1) para la clase `APIServiceFastAPI` del UML
(ver docs/uml/diagrama_clases.puml). La implementación completa —
conexión real a MySQL, motor de alertas y WebSockets— corresponde a los
Sprints 3 (Semanas 5-6) del cronograma.

Por ahora expone los mismos dos endpoints de solo lectura definidos en el
UML (getEstadoClima / getAlertas) devolviendo datos de ejemplo, para que el
equipo de dashboard pueda empezar a integrar el consumo de la API sin
esperar a que la capa de persistencia esté conectada.
"""
from datetime import datetime, timezone

from fastapi import FastAPI

app = FastAPI(
    title="Monitoreo Ambiental en Tiempo Real - API",
    description="Expone el estado del clima/calidad del aire y las alertas activas.",
    version="0.1.0",
)

# TODO (Sprint 3, Semana 5): reemplazar estos datos de ejemplo por consultas
# reales a MySQL (ver src/database/schema.sql) a través de un DatabaseManager
# equivalente al de C++, o conectando directamente con un driver async
# (por ejemplo aiomysql / SQLAlchemy async).
_ESTADO_CLIMA_EJEMPLO = {
    "ciudad": "Ciudad de Mexico",
    "temperatura_actual": 24.0,
    "calidad_aire": "Normal",
    "pm2_5": 18.0,
    "co2": 420,
    "pm2_5_promedio_24h": 32.0,
    "actualizado": None,
}

_ALERTAS_EJEMPLO = [
    {"sensor_id": "sensor_03", "metrica": "pm25", "nivel": "critico", "valor_medido": 85.0, "valor_limite": 75.0},
    {"sensor_id": "sensor_02", "metrica": "pm25", "nivel": "advertencia", "valor_medido": 48.2, "valor_limite": 35.0},
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
