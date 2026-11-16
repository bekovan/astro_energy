# ASTRO Energy

[![Validate](https://github.com/bekovan/astro_energy/actions/workflows/validate.yaml/badge.svg)](https://github.com/bekovan/astro_energy/actions/workflows/validate.yaml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)

Home Assistant integration for **ASTRO Energy TM-L series micro inverters**, read
locally through the inverter's Solarman V5 data logger. No cloud account, no
vendor app, no internet access.

![ASTRO Energy](custom_components/astro_energy/brand/logo.png)

## Features

- **Local polling** — talks to the data logger over your LAN; nothing leaves the network.
- **Read-only** — the integration never writes to the inverter.
- **14 sensors** per inverter: both PV strings, AC output, temperature and lifetime energy.
- **Fixed 60-second poll** — the inverter needs several seconds to assemble an answer, so the interval is not user-configurable.
- **Survives the night** — lifetime energy keeps its value while the inverter is powered down.
- **Diagnostics and system health** for bug reports and quick checks.

## Requirements

| | |
|---|---|
| Home Assistant | 2026.9.0 or newer |
| Inverter | ASTRO Energy TM-L800Mi (the register map was reverse engineered from this model) |
| Data logger | Solarman V5 stick on the inverter's RS485 port, reachable on TCP port 8899 |

The integration depends on Home Assistant's `modbus` integration, which supplies
the `modbus-connection` library used for the register reads..

> The data logger serves one client at a time. Close the Solarman app, or any
> other tool talking to the stick, while Home Assistant is polling — otherwise
> the reads time out. 
> Best performance was obtained by blocking the access from the inverter or the internet.

## Installation

### HACS (recommended)

1. In HACS, open **Integrations** and choose **Custom repositories** from the ⋮ menu.
2. Add `https://github.com/bekovan/astro_energy` with category **Integration**.
3. Install **ASTRO Energy** and restart Home Assistant.

### Manual

Copy `custom_components/astro_energy` into your Home Assistant
`config/custom_components/` directory and restart.

## Configuration

Go to **Settings → Devices & services → Add integration → ASTRO Energy**.

| Field | Default | Description |
|---|---|---|
| Host | — | Host name or IP address of the data logger |
| Port | 8899 | TCP port of the V5 service |
| Modbus unit ID | 1 | Slave address of the inverter; almost always 1 |
| Data logger serial | *auto* | Leave empty to learn it from the logger's first answer |

Before the entry is created the integration reads the inverter once. A
30-second timeout turns an unreachable device into a clear `cannot_connect`
error instead of a broken config entry. Each inverter gets its own entry, and
adding the same host, port and unit ID twice is refused.

### Why the serial is optional

The logger ignores any frame carrying a serial other than its own, but it
stamps that serial into every reply. Leaving the field empty lets the
integration learn it on the first successful read and reuse it for later polls.

## Sensors

| Sensor | Unit | Notes |
|---|---|---|
| PV1 voltage / PV2 voltage | V | |
| PV1 current / PV2 current | A | Scale still under investigation; may read high |
| PV1 power / PV2 power | W | Calculated from voltage × current |
| DC power | W | PV1 power + PV2 power |
| AC voltage | V | |
| AC current | A | |
| AC frequency | Hz | |
| AC power | W | Community register map; compare against your meter |
| Temperature | °C | No settled offset; treat as indicative |
| Total energy | kWh | Lifetime, `total_increasing`, restored across restarts |
| MPPT trackers | — | Diagnostic |

All sensors except **Total energy** become unavailable when a poll fails.
**Total energy** stays available and holds its last value, so an inverter that
powers down overnight does not punch a gap into the Energy dashboard's
long-term statistics.

## Polling

The poll interval is fixed at 60 seconds and is deliberately not configurable:
the inverter takes several seconds per answer, so a shorter interval would
queue up requests it cannot serve. If a poll fails the coordinator retries on
the next cycle, and after three consecutive timeouts it drops the TCP link and
reconnects, because a bridge can otherwise hold a dead socket open forever.

## Troubleshooting

### `cannot_connect` while adding the integration

- The logger is not reachable at host:8899 — check the address and that nothing
  else is holding the connection.
- The unit ID is wrong.
- The inverter is completely powered down (no sun and no grid). The logger may
  still answer, but the inverter will not.

### Sensors show *unavailable*

The last poll failed. The integration retries every 60 seconds; check the log
for `No answer from the inverter` or `Could not refresh readings`. A single
failed block is logged as a warning and does not take the entry down.

### `invalid_serial`

The serial field only accepts digits. Clear it to auto-detect instead.

### Reporting a bug

Open the integration's page and choose **⋯ → Download diagnostics**. The host is
redacted; the raw telemetry block is included, which is exactly what a register
map problem needs. **Settings → System → System information** additionally
shows, per inverter, whether the last update succeeded and the last exception.

## Device library

The register map and device object live in `custom_components/astro_energy/vendor/astro_modbus/`.
That package has no Home Assistant imports and depends only on `modbus-connection`,
so it can be tested on its own and lifted into a standalone package unchanged.

## Removing

Delete the config entry under **Settings → Devices & services**, then remove the
integration through HACS (or delete the folder if installed manually). Removing
the entry deletes its entities and device; long-term statistics you already
recorded are kept.

## License

[MIT](LICENSE.txt)
