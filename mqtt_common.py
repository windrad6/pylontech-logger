import configparser
import os
import pathlib
import time

import paho.mqtt.client as mqtt

REPO_ROOT = pathlib.Path(__file__).resolve().parent
CONFIG_PATH = pathlib.Path(os.environ.get("CONFIG_PATH", REPO_ROOT / "config.ini"))

_config = configparser.ConfigParser()
_config.read(CONFIG_PATH)


def _setting(option: str, env_var: str, default):
    """config.ini's [mqtt] section overrides the env var/default, so the
    internal broker (set via env vars in docker-compose.yml) keeps working
    unchanged unless the user explicitly points config.ini at another one."""
    value = _config.get("mqtt", option, fallback="").strip()
    if value:
        return value
    return os.environ.get(env_var, default)


MQTT_HOST = _setting("host", "MQTT_HOST", "localhost")
MQTT_PORT = int(_setting("port", "MQTT_PORT", "1883"))
MQTT_USER = _setting("user", "MQTT_USER", "") or None
MQTT_PASSWORD = _setting("password", "MQTT_PASSWORD", "") or None
TOPIC_PREFIX = os.environ.get("MQTT_TOPIC_PREFIX", "pylontech")


def data_topic(stack: str, addr: int) -> str:
    return f"{TOPIC_PREFIX}/{stack}/{addr}"


def connect(client_id: str) -> mqtt.Client:
    """Create an MQTT client and connect, retrying until the broker is reachable."""
    client = mqtt.Client(client_id=client_id, callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT)
            return client
        except OSError as e:
            print(f"Could not reach MQTT broker at {MQTT_HOST}:{MQTT_PORT} ({e}), retrying in 2s")
            time.sleep(2)
