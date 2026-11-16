"""System health platform for the ASTRO Energy integration."""

from typing import Any

from homeassistant.components.system_health import SystemHealthRegistration
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


@callback
def async_register(hass: HomeAssistant, register: SystemHealthRegistration) -> None:
    """Register the system health callback."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Report whether each configured inverter is answering."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    inverters: list[dict[str, Any]] = []
    for entry in entries:
        coordinator = getattr(entry.runtime_data, "coordinator", None)
        if coordinator is None:
            continue
        inverters.append(
            {
                "title": entry.title,
                "last_update_success": coordinator.last_update_success,
                "last_exception": str(coordinator.last_exception)
                if coordinator.last_exception
                else None,
            }
        )
    return {"configured_inverters": len(inverters), "inverters": inverters}
