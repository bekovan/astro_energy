"""DataUpdateCoordinator for the ASTRO Energy integration."""

from __future__ import annotations

from datetime import timedelta
from functools import cached_property
from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from modbus_connection import ModbusError, ModbusTimeoutError
from modbus_connection.model import UpdateReport

from .const import DOMAIN, LOGGER
from .vendor.astro_modbus import MANUFACTURER, MODEL

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from homeassistant.core import HomeAssistant

    from .data import AstroEnergyConfigEntry
    from .vendor.astro_modbus import AstroInverter

#: A link that is up but silent is recycled after this many timeouts in a row.
TIMEOUTS_BEFORE_DISCONNECT = 3


class AstroEnergyCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Poll one inverter and hand the update report to the entities."""

    config_entry: AstroEnergyConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AstroEnergyConfigEntry,
        device: AstroInverter,
        poll: Callable[[], Awaitable[UpdateReport]],
        interval: timedelta,
    ) -> None:
        """Initialize the coordinator for one inverter."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=interval,
        )
        self.device = device
        self._poll = poll
        self._timeouts = 0

    @cached_property
    def device_info(self) -> DeviceInfo:
        """Describe the inverter to the device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=self.config_entry.title,
        )

    async def _async_update_data(self) -> UpdateReport:
        """Poll the inverter and report what refreshed."""
        try:
            report = await self._poll()
        except ModbusTimeoutError as err:
            self._timeouts += 1
            if self._timeouts >= TIMEOUTS_BEFORE_DISCONNECT:
                # A bridge that keeps the socket open while the inverter stopped
                # answering never reconnects on its own, so recycle the link.
                LOGGER.debug("Recycling the Modbus link after repeated timeouts")
                await self.device.modbus_unit.disconnect()
                self._timeouts = 0
            raise UpdateFailed(f"No answer from the inverter: {err}") from err
        except ModbusError as err:
            raise UpdateFailed(str(err)) from err
        finally:
            # Disconnect after each poll to avoid stream desync issues
            try:
                await self.device.modbus_unit.disconnect()
            except Exception:
                pass

        self._timeouts = 0
        if not report.updated:
            first = next(iter(report.failed.values()), None)
            raise UpdateFailed(f"No data from the inverter: {first}") from first
        for name in sorted(report.failed):
            LOGGER.warning("Could not refresh %s: %s", name, report.failed[name])
        return report
