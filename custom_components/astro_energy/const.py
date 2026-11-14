"""Constants for the ASTRO Energy integration."""

from __future__ import annotations

from logging import Logger, getLogger
from typing import Final

LOGGER: Logger = getLogger(__package__)

DOMAIN: Final = "astro_energy"

DEFAULT_SCAN_INTERVAL: Final = 60
MIN_SCAN_INTERVAL: Final = 10
MAX_SCAN_INTERVAL: Final = 3600
CONF_SCAN_INTERVAL: Final = "scan_interval"

CONF_UNIT_ID: Final = "unit_id"
CONF_LOGGER_SERIAL: Final = "logger_serial"
"""Serial number of the Solarman V5 data logger; learned on the first read."""

DEFAULT_PORT: Final = 8899
DEFAULT_UNIT_ID: Final = 1

#: The inverter needs several seconds per answer; keep the form from hanging.
CONNECT_TIMEOUT: Final = 30
