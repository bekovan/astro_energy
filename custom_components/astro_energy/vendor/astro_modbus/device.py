"""The top-level device object for an ASTRO Energy TM-L micro inverter."""

from collections.abc import Iterable

from modbus_connection import ModbusUnit
from modbus_connection.model import Device, Raw, UpdateReport

from .readings import Readings

MANUFACTURER = "ASTRO Energy"
"""Name the device reports in the Home Assistant device registry."""

MODEL = "TM-L800Mi"
"""Model this register map was reverse engineered from."""

#: Attribute names each update method refreshes.
READINGS = ("readings",)
ALL = READINGS

#: The inverter takes several seconds to assemble telemetry, so the link's
#: default 10 s request timeout is too tight for it.
REQUIRED_TIMEOUT = 20.0


class AstroInverter(Device):
    """An ASTRO Energy TM-L micro inverter reached through a ``ModbusUnit``."""

    def __init__(self, unit: ModbusUnit) -> None:
        """Bind the device to one unit on a shared Modbus connection."""
        super().__init__(unit)
        self.readings = Readings(unit)

    async def _async_setup(self) -> None:
        """Ask the link for the timing this inverter needs."""
        self.modbus_unit.require_timeout(REQUIRED_TIMEOUT)

    async def async_update_readings(self) -> UpdateReport:
        """Refresh the telemetry block."""
        return await self.async_poll(READINGS)

    async def async_update(self) -> UpdateReport:
        """Refresh every sub-system this device has."""
        return await self.async_poll(READINGS)

    async def async_read_raw(self, names: Iterable[str] = ALL) -> Raw:
        """Return the raw register map, undecoded, for diagnostics."""
        return await super().async_read_raw(names)
