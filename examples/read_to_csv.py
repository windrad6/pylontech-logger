import configparser
import logging
import pathlib
import pylontech
import subprocess, tempfile, time, sys
from datetime import datetime
import coloredlogs
coloredlogs.install(level="DEBUG")

logger = logging.getLogger(__name__)

sys.path.append(str(pathlib.Path(__file__).parent.parent))
from csvWiter import csvWriter
from avg import avg

def parseCsvLine(data):
    r = [
        data["CycleNumber"],
        data["AverageBMSTemperature"],
        data["Current"],
        data["Power"],
        data["RemainingCapacity"],
        data["StateOfCharge"],
        data["TotalCapacity"],
        data["TotalPower"],
        data["Voltage"],
        data["GroupedCellsTemperatures"][0],
        data["GroupedCellsTemperatures"][1],
        data["GroupedCellsTemperatures"][2],
        data["GroupedCellsTemperatures"][3],
        data["CellVoltages"][0],
        data["CellVoltages"][1],
        data["CellVoltages"][2],
        data["CellVoltages"][3],
        data["CellVoltages"][4],
        data["CellVoltages"][5],
        data["CellVoltages"][6],
        data["CellVoltages"][7],
        data["CellVoltages"][8],
        data["CellVoltages"][9],
        data["CellVoltages"][10],
        data["CellVoltages"][11],
        data["CellVoltages"][12],
        data["CellVoltages"][13],
        data["CellVoltages"][14]
    ]

    return r

def genHeader():
    r = [
        "CycleNumber",
        "AverageBMSTemperature",
        "Current",
        "Power",
        "RemainingCapacity",
        "StateOfCharge",
        "TotalCapacity",
        "TotalPower",
        "Voltage",
        "GroupedCellsTemperatures0",
        "GroupedCellsTemperatures1",
        "GroupedCellsTemperatures2",
        "GroupedCellsTemperatures3",
        "CellVoltages0",
        "CellVoltages1",
        "CellVoltages2",
        "CellVoltages3",
        "CellVoltages4",
        "CellVoltages5",
        "CellVoltages6",
        "CellVoltages7",
        "CellVoltages8",
        "CellVoltages9",
        "CellVoltages10",
        "CellVoltages11",
        "CellVoltages12",
        "CellVoltages13",
        "CellVoltages14",
    ]

    return r


config = configparser.ConfigParser()
config.read(pathlib.Path(__file__).parent / "config.ini")

tmpDir = tempfile.mkdtemp(prefix="pylontech-")

batList = {}
for section in config.sections():
    batList[section] = {
        "addr": [int(a.strip()) for a in config[section]["addr"].split(",")],
        "dev": str(pathlib.Path(tmpDir) / section),
        "ip": config[section]["ip"],
        "port": config[section]["port"],
    }

batCSVList = {}
batHandle = {}
avgObj = {}

logger.info("Create sockets")
for elm in batList:
    logger.info(f"Probing battery stack {elm} ({batList[elm]['ip']}:{batList[elm]['port']})")
    subprocess.Popen(["/usr/bin/socat", "pty,link=" + batList[elm]["dev"] + ",waitslave", "tcp:" + batList[elm]["ip"] + ":" + batList[elm]["port"]])
    time.sleep(1)# wait a second to create the socket
    batHandle.update({elm : pylontech.Pylontech(serial_port=batList[elm]["dev"])})

    #creat csv object per battery
    for addr in batList[elm]["addr"]:
        batCSVList.update({str(addr) : csvWriter(str(pathlib.Path(__file__).parent / "data"), "bat_" + str(addr), delimiter = ";", flushLines = 1)})
        header = genHeader()
        header.insert(0, "Count")
        header.insert(0, "Date")
        batCSVList[str(addr)].setHeader(header)
        avgObj.update({str(addr) : avg("minute")})
logger.info("Start reading data")
while True:
    for elm in batList:
        for addr in batList[elm]["addr"]:
            data = parseCsvLine(batHandle[elm].get_values_single(addr))

            if avgObj[str(addr)].checkTime(datetime.now()):
                avgStarttime = avgObj[str(addr)].getStarttime()
                count = avgObj[str(addr)].getCount()
                lineData = avgObj[str(addr)].getData()
                lineData.insert(0, count)
                timeStr = f"{avgStarttime.strftime('%d/%m/%Y %H:%M:00')}"
                lineData.insert(0, timeStr)

                batCSVList[str(addr)].writeLine(lineData)

            avgObj[str(addr)].add(data)
            #logger.debug(f"Read data from address {addr}")
