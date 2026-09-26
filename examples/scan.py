import configparser
import logging
import pathlib
import subprocess, tempfile, time
import pylontech
import coloredlogs
coloredlogs.install(level="DEBUG")

logger = logging.getLogger(__name__)

SCAN_START = 0
SCAN_END = 30

config = configparser.ConfigParser()
config.read(pathlib.Path(__file__).parent / "config.ini")

tmpDir = tempfile.mkdtemp(prefix="pylontech-")

batList = {}
for section in config.sections():
    batList[section] = {
        "dev": str(pathlib.Path(tmpDir) / section),
        "ip": config[section]["ip"],
        "port": config[section]["port"],
    }

batHandle = {}
for elm in batList:
    subprocess.Popen(["/usr/bin/socat", "pty,link=" + batList[elm]["dev"] + ",waitslave", "tcp:" + batList[elm]["ip"] + ":" + batList[elm]["port"]])
    time.sleep(1)# wait a second to create the socket
    batHandle.update({elm : pylontech.Pylontech(serial_port=batList[elm]["dev"])})

found = {}
for elm in batList:
    logger.info(f"Probing battery stack {elm} ({batList[elm]['ip']}:{batList[elm]['port']})")
    found[elm] = batHandle[elm].scan_for_batteries(SCAN_START, SCAN_END)

print("\nScan results:")
for elm in found:
    for addr, sn in found[elm].items():
        print(f"{elm}: address {addr}\tserial {sn}")

print("\nAdd this to config.ini:")
for elm in found:
    addrs = ",".join(str(addr) for addr in found[elm])
    print(f"addr = {addrs}\t# {elm}")
