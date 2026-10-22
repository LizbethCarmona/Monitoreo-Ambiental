"""Validacion y persistencia transaccional de lecturas publicadas por MQTT."""
from __future__ import annotations

import json
import math
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from mysql.connector import Error as MySQLError

from . import db

_TOPIC_SENSOR = re.compile(r"^monitoreo/lecturas/([A-Za-z0-9][A-Za-z0-9_.-]{0,49})$")
_METRICAS = (
    ("pm25", "pm2.5"),
    ("co2", "co2"),
    ("tmp", "tmp"),
)


@dataclass(frozen=True)
class LecturaValidada:
    sensor_id: str
    pm25: float
    co2: float
    tmp: float
    timestamp: datetime


def validar_mensaje_mqtt(topic: str, payload: bytes) -> LecturaValidada:
    coincidencia = _TOPIC_SENSOR.fullmatch(topic)
    if coincidencia is None:
        raise ValueError("El topic debe tener el formato monitoreo/lecturas/{sensor_id}.")

    try:
        contenido: Any = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("El payload MQTT debe ser JSON UTF-8 valido.") from exc
    if not isinstance(contenido, dict):
        raise ValueError("El payload MQTT debe ser un objeto JSON.")

    sensor_id = contenido.get("sensor_id")
    if sensor_id != coincidencia.group(1):
        raise ValueError("El sensor_id del JSON debe coincidir con el topic MQTT.")

    valores = {}
    limites = {"pm2.5": 9999.99, "co2": 99999.99, "tmp": 999.99}
    for campo, limite in limites.items():
        valor = contenido.get(campo)
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise ValueError(f"La metrica {campo} debe ser numerica.")
        valor_float = float(valor)
        if not math.isfinite(valor_float) or not 0 <= valor_float <= limite:
            raise ValueError(f"La metrica {campo} debe estar entre 0 y {limite}.")
        valores[campo] = valor_float

    marca = contenido.get("timestamp")
    if not isinstance(marca, str):
        raise ValueError("timestamp debe ser una fecha ISO-8601 con zona horaria.")
    try:
        timestamp = datetime.fromisoformat(marca.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp debe ser una fecha ISO-8601 valida.") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("timestamp debe incluir su zona horaria.")

    return LecturaValidada(
        sensor_id=sensor_id,
        pm25=valores["pm2.5"],
        co2=valores["co2"],
        tmp=valores["tmp"],
        timestamp=timestamp.astimezone(timezone.utc),
    )


def elegir_alerta(lectura: LecturaValidada, umbrales: dict) -> tuple | None:
    candidatos = []
    for metrica, campo in _METRICAS:
        valor = getattr(lectura, "pm25" if metrica == "pm25" else metrica)
        for nivel in ("critico", "advertencia"):
            limite = umbrales.get((metrica, nivel, "lectura"))
            if limite is not None and valor >= limite:
                candidatos.append((nivel, metrica, valor, limite))
                break

    for nivel_preferido in ("critico", "advertencia"):
        for nivel, metrica, valor, limite in candidatos:
            if nivel == nivel_preferido:
                return metrica, nivel, valor, limite
    return None


def persistir_lectura_mqtt(lectura: LecturaValidada) -> str:
    conn = db.conectar()
    try:
        cursor = conn.cursor()
        conn.start_transaction()
        cursor.execute(
            "INSERT IGNORE INTO sensores (sensor_id, nombre) VALUES (%s, %s)",
            (lectura.sensor_id, lectura.sensor_id),
        )
        cursor.execute(
            "INSERT INTO lecturas (sensor_id, pm25, co2, tmp, timestamp_lectura) "
            "VALUES (%s, %s, %s, %s, %s)",
            (
                lectura.sensor_id,
                lectura.pm25,
                lectura.co2,
                lectura.tmp,
                lectura.timestamp.replace(tzinfo=None),
            ),
        )
        lectura_id = cursor.lastrowid
        cursor.execute("SELECT metrica, nivel, valor_limite FROM umbrales WHERE aplica_a = 'lectura'")
        umbrales = {
            (metrica, nivel, "lectura"): float(limite)
            for metrica, nivel, limite in cursor.fetchall()
        }
        alerta = elegir_alerta(lectura, umbrales)
        if alerta is not None:
            metrica, nivel, valor, limite = alerta
            cursor.execute(
                "INSERT INTO alertas (lectura_id, sensor_id, metrica, nivel, valor_medido, "
                "valor_limite, mensaje) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    lectura_id,
                    lectura.sensor_id,
                    metrica,
                    nivel,
                    valor,
                    limite,
                    f"{metrica} sobre umbral de lectura MQTT",
                ),
            )
        conn.commit()
        return "guardada"
    except MySQLError as exc:
        conn.rollback()
        if exc.errno == 1062:
            return "duplicada"
        raise
    finally:
        conn.close()


class IngestorMQTT:
    def __init__(self) -> None:
        self.host = os.getenv("MQTT_HOST", "127.0.0.1")
        self.port = int(os.getenv("MQTT_PORT", "1883"))
        self.topic = os.getenv("MQTT_TOPIC", "monitoreo/lecturas/+")
        self.client_id = os.getenv("MQTT_CLIENT_ID", "monitoreo-api")
        self._client = None
        self._estado = "detenido"
        self._guardadas = 0
        self._duplicadas = 0
        self._errores = 0
        self._ultimo_error: str | None = None
        self._lock = threading.Lock()

    @property
    def estado(self) -> dict:
        with self._lock:
            return {
                "estado": self._estado,
                "host": self.host,
                "puerto": self.port,
                "topic": self.topic,
                "guardadas": self._guardadas,
                "duplicadas": self._duplicadas,
                "errores": self._errores,
                "ultimo_error": self._ultimo_error,
            }

    def iniciar(self) -> None:
        if self._client is not None:
            return
        import paho.mqtt.client as mqtt

        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.client_id,
            protocol=mqtt.MQTTv311,
            manual_ack=True,
        )
        usuario = os.getenv("MQTT_USERNAME")
        clave = os.getenv("MQTT_PASSWORD")
        if usuario and not clave:
            raise RuntimeError("MQTT_PASSWORD es obligatoria cuando se configura MQTT_USERNAME.")
        if usuario:
            client.username_pw_set(usuario, clave)
        if os.getenv("MQTT_TLS_ENABLED", "false").strip().lower() in {"1", "true", "yes"}:
            client.tls_set()
        client.on_connect = self._al_conectar
        client.on_disconnect = self._al_desconectar
        client.on_message = self._al_mensaje
        self._client = client
        with self._lock:
            self._estado = "conectando"
            self._ultimo_error = None
        client.connect_async(self.host, self.port, keepalive=30)
        client.loop_start()

    def detener(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            client.disconnect()
            client.loop_stop()
        with self._lock:
            self._estado = "detenido"

    def _al_conectar(self, client, _userdata, _flags, reason_code, _properties) -> None:
        if reason_code.is_failure:
            error = f"El broker MQTT rechazo la conexion: {reason_code}"
            with self._lock:
                self._estado = "degradado"
                self._ultimo_error = error
            return
        client.subscribe(self.topic, qos=1)
        with self._lock:
            self._estado = "conectado"
            self._ultimo_error = None

    def _al_desconectar(self, _client, _userdata, _disconnect_flags, reason_code, _properties) -> None:
        with self._lock:
            self._estado = "desconectado" if reason_code.is_failure else "detenido"
            if reason_code.is_failure:
                self._ultimo_error = f"Se perdio la conexion con MQTT: {reason_code}"

    def _al_mensaje(self, client, _userdata, mensaje) -> None:
        try:
            lectura = validar_mensaje_mqtt(mensaje.topic, mensaje.payload)
            resultado = persistir_lectura_mqtt(lectura)
            client.ack(mensaje.mid, mensaje.qos)
            with self._lock:
                if resultado == "guardada":
                    self._guardadas += 1
                else:
                    self._duplicadas += 1
        except ValueError as exc:
            with self._lock:
                self._errores += 1
                self._ultimo_error = str(exc)
            import logging

            logging.getLogger(__name__).exception("Se rechazo una lectura MQTT.")
            client.ack(mensaje.mid, mensaje.qos)
        except MySQLError as exc:
            with self._lock:
                self._errores += 1
                self._estado = "degradado"
                self._ultimo_error = str(exc)
            import logging

            logging.getLogger(__name__).exception(
                "Fallo MySQL al persistir una lectura MQTT; se conserva sin ACK para reintento."
            )
