CELL_VOLTAGE_COUNT = 15
GROUPED_TEMP_COUNT = 4

SCALAR_FIELDS = [
    "CycleNumber",
    "AverageBMSTemperature",
    "Current",
    "Power",
    "RemainingCapacity",
    "StateOfCharge",
    "TotalCapacity",
    "TotalPower",
    "Voltage",
]


def to_dict(data) -> dict:
    """Convert a construct result from Pylontech.get_values_single() into a
    plain, JSON-serializable dict."""
    d = {field: data[field] for field in SCALAR_FIELDS}
    d["GroupedCellsTemperatures"] = list(data["GroupedCellsTemperatures"])
    d["CellVoltages"] = list(data["CellVoltages"])
    return d


def header() -> list:
    """CSV header matching the row layout produced by to_row()."""
    r = list(SCALAR_FIELDS)
    r += [f"GroupedCellsTemperatures{i}" for i in range(GROUPED_TEMP_COUNT)]
    r += [f"CellVoltages{i}" for i in range(CELL_VOLTAGE_COUNT)]
    return r


def to_row(d: dict) -> list:
    """Flatten a to_dict() result into the row layout matching header()."""
    r = [d[field] for field in SCALAR_FIELDS]
    r += d["GroupedCellsTemperatures"]
    r += d["CellVoltages"]
    return r


# Best-effort model label derived from a module's rated total capacity (Ah).
#
# The Pylontech RS485 protocol's CID2 0x51 "get manufacturer info" command is
# not addressable per module - independent implementations (python-pylontech
# and github.com/marevers/energia) both always send it to a fixed/host
# address regardless of which battery you ask about, so every module reports
# the same device name. TotalCapacity, in contrast, genuinely is read per
# module (via the normal CID2 0x42 "get values" call), so it's the closest
# per-module signal available for guessing which model a module is.
KNOWN_CAPACITIES_AH = {
    50: "US2000 (~2.4kWh)",
    74: "US3000 (~3.5kWh)",
    100: "US5000 (~4.8kWh)",
}
CAPACITY_TOLERANCE_AH = 3


def guess_device_type(total_capacity_ah: float) -> str:
    for ah, label in KNOWN_CAPACITIES_AH.items():
        if abs(total_capacity_ah - ah) <= CAPACITY_TOLERANCE_AH:
            return label
    return f"{total_capacity_ah:.0f} Ah (unknown model)"
