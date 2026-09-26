import configparser
import pathlib
import pylontech
import subprocess, tempfile, time

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

batHandle = {}
for elm in batList:
    subprocess.Popen(["/usr/bin/socat", "pty,link=" + batList[elm]["dev"] + ",waitslave", "tcp:" + batList[elm]["ip"] + ":" + batList[elm]["port"]])
    time.sleep(1)# wait a second to create the socket
    batHandle.update({elm : pylontech.Pylontech(serial_port=batList[elm]["dev"])})


while True:
    for elm in batList:
        for addr in batList[elm]["addr"]:
            data = batHandle[elm].get_values_single(addr)
            print(  "Bat " + str(addr) + "\t" +
                    str(data["CycleNumber"]/100) + "\t" +
                    str(data["Voltage"]) + "\t" +
                    str(data["TotalCapacity"]) + "\t" +
                    str(data["RemainingCapacity"]) + "\t"
            )
            #print(batHandle[elm].get_values_single(addr))
