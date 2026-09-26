import bisect
import configparser
import json
import logging
import os
import pathlib
import sys
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import coloredlogs
from flask import Flask, jsonify, render_template, request

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent))
import mqtt_common
from history_store import HistoryStore
from pylontech_data import CELL_VOLTAGE_COUNT

coloredlogs.install(level="INFO")
logger = logging.getLogger(__name__)

HISTORY_HOURS = float(os.environ.get("HISTORY_HOURS", "1"))
HISTORY_WINDOW = timedelta(hours=HISTORY_HOURS)
MAX_POINTS = 1000  # spread evenly across the configured history window
CACHE_DIR = pathlib.Path(os.environ.get("CACHE_DIR", "/app/cache"))
METRICS = ["Voltage", "Current", "Power", "StateOfCharge", "AverageBMSTemperature", "CycleNumber"]
MAX_CELL_DELTA_MV = float(os.environ.get("MAX_CELL_DELTA_MV", "10"))

INVALID_TEMPERATURE_C = -100
TEMP_TOLERANCE = 0.5


def load_expected_module_count():
    """Total battery modules configured across all stacks in config.ini."""
    config = configparser.ConfigParser()
    config.read(mqtt_common.CONFIG_PATH)
    total = 0
    for section in config.sections():
        if section in ("mqtt", "ui"):
            continue
        total += len([a for a in config[section]["addr"].split(",") if a.strip()])
    return total


def load_clear_cache_password():
    config = configparser.ConfigParser()
    config.read(mqtt_common.CONFIG_PATH)
    return config.get("ui", "clear_cache_password", fallback=None)


EXPECTED_MODULE_COUNT = load_expected_module_count()
CLEAR_CACHE_PASSWORD = load_clear_cache_password()


def clean_temp(value):
    """Pylontech modules report -100°C for an unpopulated temperature sensor; treat it as missing."""
    if value is not None and abs(value - INVALID_TEMPERATURE_C) < TEMP_TOLERANCE:
        return None
    return value

app = Flask(__name__)

lock = threading.Lock()
latest = {}                    # (stack, addr) -> payload dict
history = defaultdict(deque)   # (stack, addr) -> deque[(datetime, payload dict)]
store = HistoryStore(CACHE_DIR / "history.sqlite3")


def retention_cutoff(now):
    return (now - HISTORY_WINDOW).isoformat()


def load_cache():
    """Repopulate in-memory history/latest from the on-disk cache so a
    restart doesn't lose data still inside the retention window."""
    cutoff = retention_cutoff(datetime.now(timezone.utc))
    rows_by_key = store.load_recent(cutoff)
    for (stack, addr), rows in rows_by_key.items():
        key = (stack, addr)
        for ts_iso, payload in rows:
            history[key].append((datetime.fromisoformat(ts_iso), payload))
        if rows:
            latest[key] = rows[-1][1]
    if rows_by_key:
        logger.info(f"Restored {sum(len(r) for r in rows_by_key.values())} cached readings for {len(rows_by_key)} battery/batteries")


def prune(key, now):
    dq = history[key]
    while dq and now - dq[0][0] > HISTORY_WINDOW:
        dq.popleft()


def on_connect(client, userdata, flags, reason_code, properties):
    logger.info(f"Connected to MQTT broker (reason={reason_code})")
    client.subscribe(f"{mqtt_common.TOPIC_PREFIX}/+/+")


def on_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode())
    payload["AverageBMSTemperature"] = clean_temp(payload.get("AverageBMSTemperature"))
    if "GroupedCellsTemperatures" in payload:
        payload["GroupedCellsTemperatures"] = [clean_temp(t) for t in payload["GroupedCellsTemperatures"]]

    key = (payload["stack"], payload["addr"])
    now = datetime.fromisoformat(payload["timestamp"])

    with lock:
        latest[key] = payload
        history[key].append((now, payload))
        prune(key, now)
        store.append(key[0], key[1], payload["timestamp"], payload)
        store.prune(retention_cutoff(now))
        store.commit()


def safe_avg(values):
    """Average, ignoring None entries (e.g. a temperature sensor reading masked by clean_temp)."""
    valid = [v for v in values if v is not None]
    return sum(valid) / len(valid) if valid else None


def downsample(rows, max_points=MAX_POINTS):
    """Bucket-average rows down to at most max_points, keeping all metrics aligned."""
    if len(rows) <= max_points:
        return rows

    start = rows[0][0]
    end = rows[-1][0]
    span = (end - start).total_seconds() or 1
    bucket_seconds = span / max_points

    buckets = {}
    for ts, vals in rows:
        idx = int((ts - start).total_seconds() // bucket_seconds)
        buckets.setdefault(idx, []).append((ts, vals))

    result = []
    for idx in sorted(buckets):
        bucket = buckets[idx]
        ts = bucket[-1][0]
        avgVals = {m: safe_avg([v[m] for _, v in bucket]) for m in METRICS}
        avgVals["CellVoltages"] = [
            safe_avg([v["CellVoltages"][i] for _, v in bucket]) for i in range(CELL_VOLTAGE_COUNT)
        ]
        result.append((ts, avgVals))
    return result


def build_system_history(max_points=360):
    """Sum every battery's power (and average voltage) into shared time buckets.

    Batteries report asynchronously, so for each bucket time we take each
    battery's most recent known reading at-or-before that time (last value
    carried forward) rather than only summing whatever happens to land in the
    exact same bucket - otherwise readings that don't line up in time would
    silently drop out of the total.
    """
    with lock:
        series = {}
        start = end = None
        for key, dq in history.items():
            rows = list(dq)
            if not rows:
                continue
            ts_list = [r[0] for r in rows]
            power_list = [r[1]["Power"] for r in rows]
            voltage_list = [r[1]["Voltage"] for r in rows]
            series[key] = (ts_list, power_list, voltage_list)
            if start is None or ts_list[0] < start:
                start = ts_list[0]
            if end is None or ts_list[-1] > end:
                end = ts_list[-1]

    if not series or start == end:
        return {"timestamps": [], "TotalPower": [], "AvgVoltage": []}

    span = (end - start).total_seconds()
    steps = min(max_points, 200)
    step_seconds = span / steps

    timestamps = []
    total_power = []
    avg_voltage = []
    for i in range(steps + 1):
        t = start + timedelta(seconds=step_seconds * i)
        powers = []
        voltages = []
        for ts_list, power_list, voltage_list in series.values():
            idx = bisect.bisect_right(ts_list, t) - 1
            if idx >= 0:
                powers.append(power_list[idx])
                voltages.append(voltage_list[idx])
        if not powers:
            continue
        timestamps.append(t.isoformat())
        total_power.append(sum(powers))
        avg_voltage.append(sum(voltages) / len(voltages))

    return {"timestamps": timestamps, "TotalPower": total_power, "AvgVoltage": avg_voltage}


@app.route("/")
def index():
    return render_template("index.html", max_cell_delta_mv=MAX_CELL_DELTA_MV, history_hours=HISTORY_HOURS)


def avg_report_interval(raw_rows):
    """Average seconds between readings, from the raw (un-downsampled) history."""
    if len(raw_rows) < 2:
        return None
    span = (raw_rows[-1][0] - raw_rows[0][0]).total_seconds()
    return span / (len(raw_rows) - 1) if span > 0 else None


@app.route("/api/snapshot")
def snapshot():
    batteries = []
    with lock:
        for key in sorted(latest.keys()):
            stack, addr = key
            raw_rows = list(history[key])
            rows = downsample(raw_rows)
            batteries.append({
                "stack": stack,
                "addr": addr,
                "latest": latest[key],
                "avgReportIntervalSeconds": avg_report_interval(raw_rows),
                "history": {
                    "timestamps": [ts.isoformat() for ts, _ in rows],
                    **{m: [vals[m] for _, vals in rows] for m in METRICS},
                    "CellVoltages": [vals["CellVoltages"] for _, vals in rows],
                },
            })
    return jsonify({
        "generatedAt": datetime.now().isoformat(),
        "batteries": batteries,
        "systemHistory": build_system_history(),
        "expectedModuleCount": EXPECTED_MODULE_COUNT,
    })


@app.route("/api/clear_cache", methods=["POST"])
def clear_cache():
    submitted = (request.get_json(silent=True) or {}).get("password")
    if not CLEAR_CACHE_PASSWORD or submitted != CLEAR_CACHE_PASSWORD:
        return jsonify({"error": "invalid password"}), 403

    with lock:
        history.clear()
        latest.clear()
        store.clear_all()

    logger.info("Cache cleared via UI")
    return jsonify({"ok": True})


if __name__ == "__main__":
    load_cache()

    mqttClient = mqtt_common.connect("pylontech-ui")
    mqttClient.on_connect = on_connect
    mqttClient.on_message = on_message
    mqttClient.loop_start()

    app.run(host="0.0.0.0", port=int(os.environ.get("UI_PORT", "9080")))
