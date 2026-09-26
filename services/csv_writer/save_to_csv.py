import configparser
import json
import logging
import os
import pathlib
import sys
from datetime import datetime

import coloredlogs

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent))
import mqtt_common
from pylontech_data import header, to_row
from csvWiter import csvWriter
from avg import avg

coloredlogs.install(level="DEBUG")
logger = logging.getLogger(__name__)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = pathlib.Path(os.environ.get("CONFIG_PATH", REPO_ROOT / "config.ini"))

config = configparser.ConfigParser()
config.read(CONFIG_PATH)

DATA_DIR = pathlib.Path(config.get("general", "data_dir", fallback="data"))
if not DATA_DIR.is_absolute():
    DATA_DIR = REPO_ROOT / DATA_DIR

batCSVList = {}
avgObj = {}


def get_key_state(addr: int):
    key = str(addr)
    if key not in batCSVList:
        writer = csvWriter(str(DATA_DIR), f"bat_{addr}", delimiter=";", flushLines=1)
        writer.setHeader(["Date", "Count"] + header())
        batCSVList[key] = writer
        avgObj[key] = avg("minute")
    return key, batCSVList[key], avgObj[key]


def on_connect(client, userdata, flags, reason_code, properties):
    logger.info(f"Connected to MQTT broker (reason={reason_code})")
    client.subscribe(f"{mqtt_common.TOPIC_PREFIX}/+/+")


def on_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode())
    addr = payload["addr"]
    key, writer, avgHandle = get_key_state(addr)
    row = to_row(payload)

    if avgHandle.checkTime(datetime.now()):
        avgStarttime = avgHandle.getStarttime()
        count = avgHandle.getCount()
        lineData = avgHandle.getData()
        lineData.insert(0, count)
        lineData.insert(0, f"{avgStarttime.strftime('%d/%m/%Y %H:%M:00')}")

        writer.writeLine(lineData)

    avgHandle.add(row)
    logger.debug(f"Buffered data from {payload['stack']} address {addr}")


client = mqtt_common.connect("pylontech-csv-writer")
client.on_connect = on_connect
client.on_message = on_message

logger.info(f"Writing CSVs to {DATA_DIR}")
client.loop_forever()
