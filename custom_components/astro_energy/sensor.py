"""Sensor platform for the ASTRO Energy integration."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AstroEnergyCoordinator
from .data import AstroEnergyConfigEntry
from .entity import AstroEnergyEntity
from .vendor.astro_modbus import AstroInverter

#: The only sub-system this device has, as named in the update report.
REPORT_NAME = "readings"


@dataclass(frozen=True, kw_only=True)
class AstroSensorEntityDescription(SensorEntityDescription):
    """Describe a sensor read straight off the device library."""

    value_fn: Callable[[AstroInverter], float | int | None]


SENSORS: tuple[AstroSensorEntityDescription, ...] = (
    AstroSensorEntityDescription(
        key="pv1_voltage",
        translation_key="pv1_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.readings.pv1_voltage,
    ),
    AstroSensorEntityDescription(
        key="pv1_current",
        translation_key="pv1_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.readings.pv1_current,
    ),
    AstroSensorEntityDescription(
        key="pv1_power",
        translation_key="pv1_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.readings.pv1_power,
    ),
    AstroSensorEntityDescription(
        key="pv2_voltage",
        translation_key="pv2_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.readings.pv2_voltage,
    ),
    AstroSensorEntityDescription(
        key="pv2_current",
        translation_key="pv2_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.readings.pv2_current,
    ),
    AstroSensorEntityDescription(
        key="pv2_power",
        translation_key="pv2_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.readings.pv2_power,
    ),
    AstroSensorEntityDescription(
        key="dc_power",
        translation_key="dc_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.readings.dc_power,
    ),
    AstroSensorEntityDescription(
        key="ac_voltage",
        translation_key="ac_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.readings.ac_voltage,
    ),
    AstroSensorEntityDescription(
        key="ac_current",
        translation_key="ac_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.readings.ac_current,
    ),
    AstroSensorEntityDescription(
        key="ac_frequency",
        translation_key="ac_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.readings.ac_frequency,
    ),
    AstroSensorEntityDescription(
        key="ac_power",
        translation_key="ac_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.readings.ac_power,
    ),
    AstroSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.readings.temperature,
    ),
    AstroSensorEntityDescription(
        key="total_energy",
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda device: device.readings.total_energy,
    ),
    AstroSensorEntityDescription(
        key="mppt_count",
        translation_key="mppt_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.readings.mppt_count,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AstroEnergyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor entities of one inverter."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        (
            AstroTotalEnergySensor
            if description.state_class is SensorStateClass.TOTAL_INCREASING
            else AstroSensor
        )(coordinator, description)
        for description in SENSORS
    )


class AstroSensor(AstroEnergyEntity, SensorEntity):
    """A measurement read from the inverter's telemetry block."""

    entity_description: AstroSensorEntityDescription

    def __init__(
        self,
        coordinator: AstroEnergyCoordinator,
        description: AstroSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def available(self) -> bool:
        """Go unavailable when the telemetry block failed to refresh."""
        return super().available and REPORT_NAME in self.coordinator.data.updated

    @property
    def native_value(self) -> float | int | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.device)


class AstroTotalEnergySensor(AstroEnergyEntity, RestoreSensor):
    """Lifetime energy: keeps its value while the inverter sleeps.

    A micro inverter powers down every night. A gap in a long-term statistic
    damages the energy dashboard, so this sensor stays available, holds its
    last value, and restores it after Home Assistant restarts.
    """

    entity_description: AstroSensorEntityDescription

    def __init__(
        self,
        coordinator: AstroEnergyCoordinator,
        description: AstroSensorEntityDescription,
    ) -> None:
        """Initialize the lifetime energy sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def available(self) -> bool:
        """Stay available while the inverter is offline."""
        return True

    async def async_added_to_hass(self) -> None:
        """Restore the last known value before the first poll lands."""
        await super().async_added_to_hass()
        if (last_data := await self.async_get_last_sensor_data()) is not None:
            self._attr_native_value = last_data.native_value
        self._process_data()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Fold a new poll into the restored value."""
        self._process_data()
        super()._handle_coordinator_update()

    def _process_data(self) -> None:
        """Take a new reading unless the device returned nothing."""
        value = self.entity_description.value_fn(self.coordinator.device)
        if value is None:
            return
        self._attr_native_value = value
