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
- `reader` — reads the battery stacks defined in [examples/config.ini](examples/config.ini) and publishes raw readings to MQTT (topic `pylontech/<stack>/<addr>`). No averaging happens here.
- `csv-writer` — subscribes to MQTT, averages each battery's readings per minute (same logic previously in `read_to_csv.py`), and writes one CSV per battery address to `./data`.
- `ui` — subscribes to MQTT and serves a dashboard at [http://localhost:8080](http://localhost:8080), grouped by stack, with live values, per-stack history charts for the last hour, and a per-battery cell voltage/temperature detail view. A battery is flagged red/"FAULTY" when its cell voltage spread exceeds `MAX_CELL_DELTA_MV` (default 10 mV, set in `docker-compose.yml`).

Edit `examples/config.ini` with your battery stacks' `addr`/`ip`/`port` (see [scan.py](examples/scan.py) to discover addresses), then run:

```
podman compose up --build
```

(or `docker compose up --build` if you're using Docker instead of Podman).

## License

Licensed under either of

* Apache License, Version 2.0, ([LICENSE-APACHE](LICENSE-APACHE) or http://www.apache.org/licenses/LICENSE-2.0)
* MIT license ([LICENSE-MIT](LICENSE-MIT) or http://opensource.org/licenses/MIT)

at your option.