import configparser
import logging
import pathlib
import subprocess, tempfile, time
import pylontech
import coloredlogs
coloredlogs.install(level="DEBUG")

logger = logging.getLogger(__name__)

config = configparser.ConfigParser()
config.read(pathlib.Path(__file__).parent.parent / "config.ini")

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

batHandle = {}
for elm in batList:
    subprocess.Popen(["/usr/bin/socat", "pty,link=" + batList[elm]["dev"] + ",waitslave", "tcp:" + batList[elm]["ip"] + ":" + batList[elm]["port"]])
    time.sleep(1)# wait a second to create the socket
    batHandle.update({elm : pylontech.Pylontech(serial_port=batList[elm]["dev"])})

for elm in batList:
    logger.info(f"Probing battery stack {elm} ({batList[elm]['ip']}:{batList[elm]['port']})")
    for addr in batList[elm]["addr"]:
        data = batHandle[elm].get_module_serial_number(addr)
        print(  "Bat " + str(addr) + "\t" +
                data["ModuleSerialNumber"].decode()
        )
