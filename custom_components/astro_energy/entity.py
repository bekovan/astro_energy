"""Base entity for the ASTRO Energy integration."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AstroEnergyCoordinator


class AstroEnergyEntity(CoordinatorEntity[AstroEnergyCoordinator]):
    """Common behaviour for every entity of this integration."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AstroEnergyCoordinator) -> None:
        """Bind the entity to its coordinator and device."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
