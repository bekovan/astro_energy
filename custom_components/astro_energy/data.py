"""Custom types for the ASTRO Energy integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .coordinator import AstroEnergyCoordinator

type AstroEnergyConfigEntry = ConfigEntry[AstroEnergyData]


@dataclass
class AstroEnergyData:
    """Runtime data held by a loaded config entry."""

    coordinator: AstroEnergyCoordinator
