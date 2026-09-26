import json
import logging
import os
import pathlib
import sys
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta

import coloredlogs
from flask import Flask, jsonify, render_template

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent))
import mqtt_common
from pylontech_data import CELL_VOLTAGE_COUNT

coloredlogs.install(level="INFO")
logger = logging.getLogger(__name__)

HISTORY_HOURS = float(os.environ.get("HISTORY_HOURS", "1"))
HISTORY_WINDOW = timedelta(hours=HISTORY_HOURS)
MAX_POINTS = 1000  # spread evenly across the configured history window
METRICS = ["Voltage", "Current", "Power", "StateOfCharge", "AverageBMSTemperature", "CycleNumber"]
MAX_CELL_DELTA_MV = float(os.environ.get("MAX_CELL_DELTA_MV", "10"))

INVALID_TEMPERATURE_C = -100
TEMP_TOLERANCE = 0.5


def clean_temp(value):
    """Pylontech modules report -100°C for an unpopulated temperature sensor; treat it as missing."""
    if value is not None and abs(value - INVALID_TEMPERATURE_C) < TEMP_TOLERANCE:
        return None
    return value

app = Flask(__name__)

lock = threading.Lock()
latest = {}                    # (stack, addr) -> payload dict
history = defaultdict(deque)   # (stack, addr) -> deque[(datetime, payload dict)]


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
    return jsonify({"generatedAt": datetime.now().isoformat(), "batteries": batteries})


if __name__ == "__main__":
    mqttClient = mqtt_common.connect("pylontech-ui")
    mqttClient.on_connect = on_connect
    mqttClient.on_message = on_message
    mqttClient.loop_start()

    app.run(host="0.0.0.0", port=int(os.environ.get("UI_PORT", "9080")))
