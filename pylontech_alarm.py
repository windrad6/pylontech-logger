"""Support for the Pylontech RS485 "Get Alarm Info" command (CID2 0x44).

This command is documented in Pylontech's RS485-protocol-pylon-low-voltage
spec (section 3.5) but is not implemented by the python-pylontech library
this project depends on, so it's implemented here instead, reusing the
low-level frame helpers (send_cmd/read_frame) already on Pylontech instances.

Response layout: per-cell voltage status, per-temperature-group status,
charge/discharge current and module voltage status (each 0x00 normal /
0x01 below limit / 0x02 above limit / 0xF0 other error), followed by five
status bitfields covering module-level protection triggers, MOSFET state
and individual cell voltage faults.
"""
import construct

STATUS_CODE_NAMES = {
    0x00: "normal",
    0x01: "below_limit",
    0x02: "above_limit",
    0xF0: "other_error",
}


def status_name(code: int) -> str:
    return STATUS_CODE_NAMES.get(code, f"unknown_0x{code:02X}")


alarm_info_fmt = construct.Struct(
    "CommandValue" / construct.Byte,
    "NumberOfCells" / construct.Int8ub,
    "CellVoltageStatus" / construct.Array(construct.this.NumberOfCells, construct.Byte),
    "NumberOfTemperatures" / construct.Int8ub,
    "BMSTemperatureStatus" / construct.Byte,
    "GroupedCellTemperatureStatus" / construct.Array(construct.this.NumberOfTemperatures - 1, construct.Byte),
    "ChargeCurrentStatus" / construct.Byte,
    "ModuleVoltageStatus" / construct.Byte,
    "DischargeCurrentStatus" / construct.Byte,
    "Status1" / construct.BitStruct(
        "ModuleUnderVoltage" / construct.Flag,
        "ChargeOverTemperature" / construct.Flag,
        "DischargeOverTemperature" / construct.Flag,
        "DischargeOverCurrent" / construct.Flag,
        "_reserved3" / construct.Flag,
        "ChargeOverCurrent" / construct.Flag,
        "CellUnderVoltage" / construct.Flag,
        "ModuleOverVoltage" / construct.Flag,
    ),
    "Status2" / construct.BitStruct(
        "_reserved7_4" / construct.BitsInteger(4),
        "UsingBatteryModulePower" / construct.Flag,
        "DischargeMosfetOn" / construct.Flag,
        "ChargeMosfetOn" / construct.Flag,
        "PreMosfetOn" / construct.Flag,
    ),
    "Status3" / construct.BitStruct(
        "EffectiveChargeCurrent" / construct.Flag,
        "EffectiveDischargeCurrent" / construct.Flag,
        "HeaterOn" / construct.Flag,
        "_reserved4" / construct.Flag,
        "FullyCharged" / construct.Flag,
        "_reserved2" / construct.Flag,
        "_reserved1" / construct.Flag,
        "BuzzerOn" / construct.Flag,
    ),
    "Status4" / construct.BitStruct(
        "CellVoltageError8" / construct.Flag,
        "CellVoltageError7" / construct.Flag,
        "CellVoltageError6" / construct.Flag,
        "CellVoltageError5" / construct.Flag,
        "CellVoltageError4" / construct.Flag,
        "CellVoltageError3" / construct.Flag,
        "CellVoltageError2" / construct.Flag,
        "CellVoltageError1" / construct.Flag,
    ),
    "Status5" / construct.BitStruct(
        "CellVoltageError16" / construct.Flag,
        "CellVoltageError15" / construct.Flag,
        "CellVoltageError14" / construct.Flag,
        "CellVoltageError13" / construct.Flag,
        "CellVoltageError12" / construct.Flag,
        "CellVoltageError11" / construct.Flag,
        "CellVoltageError10" / construct.Flag,
        "CellVoltageError9" / construct.Flag,
    ),
)

STATUS1_ALARMS = [
    ("ModuleUnderVoltage", "Module under-voltage"),
    ("ChargeOverTemperature", "Charge over-temperature"),
    ("DischargeOverTemperature", "Discharge over-temperature"),
    ("DischargeOverCurrent", "Discharge over-current"),
    ("ChargeOverCurrent", "Charge over-current"),
    ("CellUnderVoltage", "Cell under-voltage"),
    ("ModuleOverVoltage", "Module over-voltage"),
]


def get_alarm_info(bat, dev_id: int):
    """Query CID2 0x44 for a single module and return the parsed construct result."""
    bdevid = "{:02X}".format(dev_id).encode()
    bat.send_cmd(dev_id, 0x44, bdevid)
    f = bat.read_frame()
    return alarm_info_fmt.parse(f.info[1:])


def to_alarm_dict(data) -> dict:
    """Convert a get_alarm_info() result into a plain, JSON-serializable dict
    with per-cell status/error info and a flat, human-readable alarm list."""
    cell_status = [status_name(c) for c in data["CellVoltageStatus"]]
    cell_error = [bool(data["Status4"][f"CellVoltageError{i}"]) for i in range(1, 9)]
    cell_error += [bool(data["Status5"][f"CellVoltageError{i}"]) for i in range(9, 17)]
    cell_error = cell_error[:len(cell_status)]

    temp_status = [status_name(data["BMSTemperatureStatus"])]
    temp_status += [status_name(t) for t in data["GroupedCellTemperatureStatus"]]
    temp_labels = ["BMS"] + [f"Group {i + 1}" for i in range(len(data["GroupedCellTemperatureStatus"]))]

    charge_current_status = status_name(data["ChargeCurrentStatus"])
    module_voltage_status = status_name(data["ModuleVoltageStatus"])
    discharge_current_status = status_name(data["DischargeCurrentStatus"])

    alarms = []
    for i, (s, err) in enumerate(zip(cell_status, cell_error), start=1):
        if s != "normal":
            alarms.append(f"Cell {i} voltage: {s}")
        if err:
            alarms.append(f"Cell {i} voltage error")
    for label, s in zip(temp_labels, temp_status):
        if s != "normal":
            alarms.append(f"{label} temperature: {s}")
    if charge_current_status != "normal":
        alarms.append(f"Charge current: {charge_current_status}")
    if module_voltage_status != "normal":
        alarms.append(f"Module voltage: {module_voltage_status}")
    if discharge_current_status != "normal":
        alarms.append(f"Discharge current: {discharge_current_status}")
    for field, label in STATUS1_ALARMS:
        if data["Status1"][field]:
            alarms.append(label)

    return {
        "CellVoltageStatus": cell_status,
        "CellVoltageError": cell_error,
        "TemperatureStatus": temp_status,
        "ChargeCurrentStatus": charge_current_status,
        "ModuleVoltageStatus": module_voltage_status,
        "DischargeCurrentStatus": discharge_current_status,
        "ChargeMosfetOn": bool(data["Status2"]["ChargeMosfetOn"]),
        "DischargeMosfetOn": bool(data["Status2"]["DischargeMosfetOn"]),
        "FullyCharged": bool(data["Status3"]["FullyCharged"]),
        "BuzzerOn": bool(data["Status3"]["BuzzerOn"]),
        "Alarms": alarms,
        "HasAlarm": len(alarms) > 0,
    }
