# Pylontech logger

This tool is build to log data of a pylontech stack with a LV hub from pylontech.

A RS485 connection to each battery bank is needed.
The adresses for the batteries need to be determined.

|Bank | Bat | Address 
|---|---|---
1 | 1 | 18
1 | 2 | 19
1 | 3 | 20
1 | 4 | 21
1 | 5 | 22
2 | 1 | 34
2 | 2 | 35
2 | 3 | 36
2 | 4 | 37
2 | 5 | 38


This verison is tested with an USR-N540 RS485 to Ethernet converter


## Create virtual serial port device (Linux)
 `socat pty,link=$HOME/bat2,waitslave tcp:10.200.8.138:32`
 `socat pty,link=$HOME/bat1,waitslave tcp:10.200.8.138:26`


## Installation

This project has python dependencies. To setup the virtual environment run

`make init`

To remove the virtual environment run

`make clean`

To enable the virtual environment (Linux) run

`source .venv/bin/activate`

## Docker/Podman stack (MQTT + CSV logging + dashboard)

`docker-compose.yml` runs the whole pipeline as separate containers:

- `mosquitto` — MQTT broker.
- `reader` — reads the battery stacks defined in [config.ini](config.ini) and publishes raw readings to MQTT (topic `pylontech/<stack>/<addr>`). No averaging happens here. Alarm info is refreshed only every `ALARM_POLL_INTERVAL_S` seconds per battery (default 10) since it changes rarely, halving the serial round trips compared to reading it on every cycle.
- `csv-writer` — subscribes to MQTT, averages each battery's readings per minute (same logic previously in `read_to_csv.py`), and writes one CSV per battery address to the folder set by `DATA_DIR` in `docker-compose.yml` (defaults to `./data`).
- `ui` — subscribes to MQTT and serves a dashboard at [http://localhost:9080](http://localhost:9080), grouped by stack, with live values, per-stack history charts, and a per-battery cell voltage/temperature detail view (including a per-cell voltage history plot and CSV/PDF export). A battery is flagged red/"FAULTY" when its cell voltage spread exceeds `MAX_CELL_DELTA_MV` (default 10 mV). The history window shown in every chart is set by `HISTORY_HOURS` (default 1 hour), both set in `docker-compose.yml`. A battery is marked stale (orange) once it hasn't reported for 2x its own average reporting interval, and offline (red, excluded from the Overview's power totals) at 5x.

Edit [config.ini](config.ini) with your battery stacks' `addr`/`ip`/`port` (see [scan.py](examples/scan.py) to discover addresses), then run:

All three services connect to the internal `mosquitto` broker by default. To use an external broker instead, fill in the `[mqtt]` section of `config.ini` (`host`, `port`, `user`, `password`) — any field left blank/commented keeps using the internal broker.

```
podman compose up --build
```

(or `docker compose up --build` if you're using Docker instead of Podman).

## License

Licensed under either of

* Apache License, Version 2.0, ([LICENSE-APACHE](LICENSE-APACHE) or http://www.apache.org/licenses/LICENSE-2.0)
* MIT license ([LICENSE-MIT](LICENSE-MIT) or http://opensource.org/licenses/MIT)

at your option.