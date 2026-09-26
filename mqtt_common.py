import os
import time

import paho.mqtt.client as mqtt

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
TOPIC_PREFIX = os.environ.get("MQTT_TOPIC_PREFIX", "pylontech")


def data_topic(stack: str, addr: int) -> str:
    return f"{TOPIC_PREFIX}/{stack}/{addr}"


def connect(client_id: str) -> mqtt.Client:
    """Create an MQTT client and connect, retrying until the broker is reachable."""
    client = mqtt.Client(client_id=client_id, callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT)
            return client
        except OSError as e:
            print(f"Could not reach MQTT broker at {MQTT_HOST}:{MQTT_PORT} ({e}), retrying in 2s")
            time.sleep(2)
