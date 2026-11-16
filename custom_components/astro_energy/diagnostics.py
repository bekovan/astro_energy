"""Diagnostics support for the ASTRO Energy integration."""

from typing import Any

from modbus_connection import ModbusError

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .data import AstroEnergyConfigEntry

TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: AstroEnergyConfigEntry,
) -> dict[str, Any]:
    """Return the raw telemetry block, which is what a bug report needs."""
    coordinator = entry.runtime_data.coordinator
    report = coordinator.data

    registers: dict[str, dict[int, int | bool]] = {}
    read_error: str | None = None
    try:
        registers = await coordinator.device.async_read_raw()
    except ModbusError as err:
        read_error = str(err)

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "entry_options": dict(entry.options),
        "last_update_success": coordinator.last_update_success,
        "updated": sorted(report.updated) if report else [],
        "failed": {name: str(err) for name, err in report.failed.items()}
        if report
        else {},
        "registers": registers,
        "read_error": read_error,
    }
