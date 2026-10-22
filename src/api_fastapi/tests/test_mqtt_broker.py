import json
import os
import time
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import paho.mqtt.client as mqtt

from app.ingestion import IngestorMQTT


@unittest.skipUnless(os.getenv("MQTT_TEST_BROKER"), "Definir MQTT_TEST_BROKER para probar un broker real.")
class PruebasBrokerMQTT(unittest.TestCase):
    def test_publicacion_llega_al_ingestor_y_se_confirma_despues_de_persistir(self):
        host = os.environ["MQTT_TEST_BROKER"]
        port = int(os.getenv("MQTT_TEST_PORT", "1883"))
        topic_root = "monitoreo/lecturas"
        sensor_id = f"sensor_{uuid.uuid4().hex[:12]}"
        payload = json.dumps(
            {
                "sensor_id": sensor_id,
                "pm2.5": 12.5,
                "co2": 450,
                "tmp": 22.5,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        ingestor = IngestorMQTT()
        ingestor.host = host
        ingestor.port = port
        ingestor.topic = f"{topic_root}/+"
        publisher = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"test-publisher-{uuid.uuid4().hex[:10]}",
            protocol=mqtt.MQTTv311,
        )
        try:
            with patch("app.ingestion.persistir_lectura_mqtt", return_value="guardada") as guardar:
                ingestor.iniciar()
                limite = time.monotonic() + 5
                while ingestor.estado["estado"] != "conectado" and time.monotonic() < limite:
                    time.sleep(0.05)
                self.assertEqual(ingestor.estado["estado"], "conectado")

                publisher.connect(host, port, keepalive=10)
                publisher.loop_start()
                resultado = publisher.publish(f"{topic_root}/{sensor_id}", payload, qos=1)
                self.assertEqual(resultado.rc, mqtt.MQTT_ERR_SUCCESS)
                resultado.wait_for_publish(timeout=5)

                limite = time.monotonic() + 5
                while ingestor.estado["guardadas"] == 0 and time.monotonic() < limite:
                    time.sleep(0.05)

                self.assertEqual(ingestor.estado["guardadas"], 1)
                self.assertEqual(ingestor.estado["errores"], 0)
                guardar.assert_called_once()
        finally:
            if publisher.is_connected():
                publisher.disconnect()
            publisher.loop_stop()
            ingestor.detener()


if __name__ == "__main__":
    unittest.main()
