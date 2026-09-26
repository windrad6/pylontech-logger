import configparser
import json
import logging
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone

import coloredlogs
import pylontech

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent))
import mqtt_common
from pylontech_alarm import get_alarm_info, to_alarm_dict
from pylontech_data import guess_device_type, to_dict

coloredlogs.install(level="DEBUG")
logger = logging.getLogger(__name__)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = pathlib.Path(os.environ.get("CONFIG_PATH", REPO_ROOT / "config.ini"))

config = configparser.ConfigParser()
config.read(CONFIG_PATH)

tmpDir = tempfile.mkdtemp(prefix="pylontech-")

batList = {}
for section in config.sections():
    if section == "general":
        continue
    batList[section] = {
        "addr": [int(a.strip()) for a in config[section]["addr"].split(",")],
        "dev": str(pathlib.Path(tmpDir) / section),
        "ip": config[section]["ip"],
        "port": config[section]["port"],
    }

if not batList:
    logger.error(f"No battery stacks configured in {CONFIG_PATH}")
    sys.exit(1)

mqttClient = mqtt_common.connect("pylontech-reader")
mqttClient.loop_start()


def read_stack(elm: str, cfg: dict):
    """Own one stack's socat link and serial connection end-to-end.

    A stack's battery modules share a single RS485 bus, so their addresses
    must be polled sequentially on this thread; separate stacks each get
    their own socket/serial connection and thread, so they run in parallel.
    """
    logger.info(f"Probing battery stack {elm} ({cfg['ip']}:{cfg['port']})")
    subprocess.Popen(["/usr/bin/socat", "pty,link=" + cfg["dev"] + ",waitslave", "tcp:" + cfg["ip"] + ":" + cfg["port"]])
    time.sleep(1)# wait a second to create the socket
    bat = pylontech.Pylontech(serial_port=cfg["dev"])

    staticInfo = {}
    for addr in cfg["addr"]:
        info = {"SerialNumber": None}
        try:
            info["SerialNumber"] = bat.get_module_serial_number(addr)["ModuleSerialNumber"].decode().strip()
        except Exception as e:
            logger.warning(f"Could not read serial number for {elm} address {addr}: {e}")
        staticInfo[addr] = info
        logger.info(f"{elm} address {addr}: serial={info['SerialNumber']}")

    logger.info(f"Start reading data for {elm}")
    while True:
        for addr in cfg["addr"]:
            try:
                data = to_dict(bat.get_values_single(addr))
                data["stack"] = elm
                data["addr"] = addr
                data["timestamp"] = datetime.now(timezone.utc).isoformat()
                data["DeviceType"] = guess_device_type(data["TotalCapacity"])
                data.update(staticInfo[addr])

                try:
                    data.update(to_alarm_dict(get_alarm_info(bat, addr)))
                except Exception as e:
                    logger.warning(f"Could not read alarm info for {elm} address {addr}: {e}")

                mqttClient.publish(mqtt_common.data_topic(elm, addr), json.dumps(data))
            except Exception as e:
                logger.error(f"Error reading {elm} address {addr}: {e}")
                time.sleep(1)# back off so a stuck connection doesn't spin the loop


threads = [
    threading.Thread(target=read_stack, args=(elm, cfg), name=f"reader-{elm}", daemon=True)
    for elm, cfg in batList.items()
]
for t in threads:
    t.start()
for t in threads:
    t.join()
