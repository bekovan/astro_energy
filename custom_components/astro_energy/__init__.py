"""Set up the ASTRO Energy integration."""

from datetime import timedelta

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_LOGGER_SERIAL, CONF_UNIT_ID, SCAN_INTERVAL
from .coordinator import AstroEnergyCoordinator
from .data import AstroEnergyConfigEntry, AstroEnergyData
from .solarman_v5 import SolarmanV5Unit
from .vendor.astro_modbus import AstroInverter

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AstroEnergyConfigEntry,
) -> bool:
    """Set up one inverter from a config entry."""
    # The inverter is reached through its Solarman V5 data logger, which wraps
    # Modbus RTU in its own frames. Nothing else shares this link, so the entry
    # closes it on unload.
    unit = SolarmanV5Unit(
        host=entry.data[CONF_HOST],
        port=int(entry.data[CONF_PORT]),
        unit_id=int(entry.data[CONF_UNIT_ID]),
        serial=entry.data.get(CONF_LOGGER_SERIAL),
    )
    entry.async_on_unload(unit.disconnect)
    device = AstroInverter(unit)

    interval = timedelta(seconds=SCAN_INTERVAL)
    coordinator = AstroEnergyCoordinator(
        hass, entry, device, device.async_update, interval
    )
    # The first read establishes the link; a failure becomes ConfigEntryNotReady.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = AstroEnergyData(coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: AstroEnergyConfigEntry,
) -> bool:
    """Unload one inverter and release its unit."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
