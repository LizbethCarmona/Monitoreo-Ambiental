"""Publica lecturas de prueba en el mismo formato que deben usar los sensores MQTT."""
from __future__ import annotations

import argparse
import json
import os
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sensores", type=int, default=3)
    parser.add_argument("--intervalo", type=float, default=2.0, help="Segundos entre lecturas por sensor.")
    args = parser.parse_args()
    if args.sensores < 1 or args.intervalo <= 0:
        parser.error("--sensores y --intervalo deben ser mayores que cero.")

    host = os.getenv("MQTT_HOST", "127.0.0.1")
    port = int(os.getenv("MQTT_PORT", "1883"))
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=os.getenv("MQTT_PUBLISHER_ID", "simulador-ambiental"),
        protocol=mqtt.MQTTv311,
    )
    usuario = os.getenv("MQTT_USERNAME")
    clave = os.getenv("MQTT_PASSWORD")
    if usuario and not clave:
        parser.error("MQTT_PASSWORD es obligatoria cuando se configura MQTT_USERNAME.")
    if usuario:
        client.username_pw_set(usuario, clave)
    if os.getenv("MQTT_TLS_ENABLED", "false").strip().lower() in {"1", "true", "yes"}:
        client.tls_set()

    client.connect(host, port, keepalive=30)
    client.loop_start()
    sensores = [f"sensor_{i + 1:02d}" for i in range(args.sensores)]
    generador = random.Random()
    print(f"Publicando lecturas de prueba al broker MQTT {host}:{port}; detener con Ctrl+C.")
    try:
        while True:
            for sensor_id in sensores:
                pm25 = generador.uniform(5.0, 55.0)
                if generador.random() < 0.08:
                    pm25 = generador.uniform(75.0, 130.0)
                lectura = {
                    "sensor_id": sensor_id,
                    "pm2.5": round(pm25, 2),
                    "co2": round(generador.uniform(380.0, 1200.0), 2),
                    "tmp": round(generador.uniform(15.0, 33.0), 2),
                    "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                }
                resultado = client.publish(
                    f"monitoreo/lecturas/{sensor_id}",
                    json.dumps(lectura, separators=(",", ":")),
                    qos=1,
                )
                resultado.wait_for_publish()
                if resultado.rc != mqtt.MQTT_ERR_SUCCESS:
                    raise RuntimeError(f"No se pudo publicar una lectura MQTT: codigo {resultado.rc}.")
                print(f"{sensor_id}: PM2.5={lectura['pm2.5']} CO2={lectura['co2']} tmp={lectura['tmp']}")
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        print("\nSimulador MQTT detenido.")
    finally:
        client.disconnect()
        client.loop_stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
