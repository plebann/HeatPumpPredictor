"""Sensor platform for Heat Pump Predictor integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MIN_TEMP,
    MAX_TEMP,
    TRANSLATION_KEY_ENERGY,
    TRANSLATION_KEY_AVG_POWER_RUNNING,
    TRANSLATION_KEY_AVG_POWER_OVERALL,
    TRANSLATION_KEY_DUTY_CYCLE,
)
from .coordinator import HeatPumpCoordinator
from .data_manager import TemperatureBucketData

_LOGGER = logging.getLogger(__name__)

@dataclass
class HeatPumpSensorEntityDescription(SensorEntityDescription):
    value_fn: Callable[[TemperatureBucketData], float | None] = None
    bucket_temp: int = 0

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: HeatPumpCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for temp in range(MIN_TEMP, MAX_TEMP + 1):
        entities.extend([
            HeatPumpSensor(coordinator, HeatPumpSensorEntityDescription(
                key=f"total_energy_{temp}", translation_key=TRANSLATION_KEY_ENERGY, bucket_temp=temp,
                device_class=SensorDeviceClass.ENERGY, native_unit_of_measurement="kWh",
                state_class=SensorStateClass.TOTAL_INCREASING, entity_registry_enabled_default=False,
                value_fn=lambda data: data.total_energy_kwh,
            )),
            HeatPumpSensor(coordinator, HeatPumpSensorEntityDescription(
                key=f"avg_power_running_{temp}", translation_key=TRANSLATION_KEY_AVG_POWER_RUNNING, bucket_temp=temp,
                device_class=SensorDeviceClass.POWER, native_unit_of_measurement="W",
                state_class=SensorStateClass.MEASUREMENT, entity_registry_enabled_default=False,
                value_fn=lambda data: data.average_power_when_running,
            )),
            HeatPumpSensor(coordinator, HeatPumpSensorEntityDescription(
                key=f"avg_power_overall_{temp}", translation_key=TRANSLATION_KEY_AVG_POWER_OVERALL, bucket_temp=temp,
                device_class=SensorDeviceClass.POWER, native_unit_of_measurement="W",
                state_class=SensorStateClass.MEASUREMENT, entity_registry_enabled_default=False,
                value_fn=lambda data: data.average_power_overall,
            )),
            HeatPumpSensor(coordinator, HeatPumpSensorEntityDescription(
                key=f"duty_cycle_{temp}", translation_key=TRANSLATION_KEY_DUTY_CYCLE, bucket_temp=temp,
                native_unit_of_measurement="%", state_class=SensorStateClass.MEASUREMENT,
                suggested_display_precision=2, entity_registry_enabled_default=False,
                value_fn=lambda data: data.duty_cycle_percent,
            )),
        ])
    
    # Add performance curve sensors (enabled by default)
    entities.extend([
        HeatPumpPerformanceCurveSensor(coordinator, "power_curve", "Power Curve"),
        HeatPumpPerformanceCurveSensor(coordinator, "duty_cycle_curve", "Duty Cycle Curve"),
        HeatPumpPerformanceCurveSensor(coordinator, "energy_distribution", "Energy Distribution"),
    ])
    
    async_add_entities(entities)
    _LOGGER.info("Created %d heat pump predictor sensors", len(entities))

class HeatPumpSensor(CoordinatorEntity[HeatPumpCoordinator], SensorEntity):
    _attr_has_entity_name = True
    entity_description: HeatPumpSensorEntityDescription

    def __init__(self, coordinator: HeatPumpCoordinator, description: HeatPumpSensorEntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info
        
        # Set explicit name with temperature
        temp = description.bucket_temp
        if description.translation_key == TRANSLATION_KEY_ENERGY:
            self._attr_name = f"Energy at {temp}°C"
        elif description.translation_key == TRANSLATION_KEY_AVG_POWER_RUNNING:
            self._attr_name = f"Running power at {temp}°C"
        elif description.translation_key == TRANSLATION_KEY_AVG_POWER_OVERALL:
            self._attr_name = f"Overall power at {temp}°C"
        elif description.translation_key == TRANSLATION_KEY_DUTY_CYCLE:
            self._attr_name = f"Duty cycle at {temp}°C"

    @property
    def native_value(self) -> float | None:
        bucket = self.coordinator.data_manager.buckets.get(self.entity_description.bucket_temp)
        if bucket and self.entity_description.value_fn:
            return self.entity_description.value_fn(bucket)
        return None


class HeatPumpPerformanceCurveSensor(CoordinatorEntity[HeatPumpCoordinator], SensorEntity):
    """Sensor providing chart-ready performance curve data."""
    
    _attr_has_entity_name = True
    
    def __init__(self, coordinator: HeatPumpCoordinator, key: str, name: str) -> None:
        """Initialize the performance curve sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_device_info = coordinator.device_info
        self._attr_name = name
        self._key = key
    
    @property
    def native_value(self) -> str:
        """Return sensor state."""
        return "ok"
    
    @property
    def extra_state_attributes(self) -> dict:
        """Return chart-ready data as attributes."""
        if self._key == "power_curve":
            return self._get_power_curve_data()
        elif self._key == "duty_cycle_curve":
            return self._get_duty_cycle_curve_data()
        elif self._key == "energy_distribution":
            return self._get_energy_distribution_data()
        return {}
    
    def _get_power_curve_data(self) -> dict:
        """Generate power consumption curve data."""
        data = []
        for temp in range(MIN_TEMP, MAX_TEMP + 1):
            bucket = self.coordinator.data_manager.buckets.get(temp)
            if bucket and bucket.total_time_seconds > 0:
                data.append({
                    "temp": temp,
                    "power_overall": round(bucket.average_power_overall, 1),
                    "power_running": round(bucket.average_power_when_running, 1),
                })
        return {"data": data}
    
    def _get_duty_cycle_curve_data(self) -> dict:
        """Generate duty cycle curve data."""
        data = []
        for temp in range(MIN_TEMP, MAX_TEMP + 1):
            bucket = self.coordinator.data_manager.buckets.get(temp)
            if bucket and bucket.total_time_seconds > 0:
                data.append({
                    "temp": temp,
                    "duty_cycle": round(bucket.duty_cycle_percent, 2),
                })
        return {"data": data}
    
    def _get_energy_distribution_data(self) -> dict:
        """Generate energy distribution data."""
        data = []
        for temp in range(MIN_TEMP, MAX_TEMP + 1):
            bucket = self.coordinator.data_manager.buckets.get(temp)
            if bucket and bucket.total_energy_kwh > 0:
                data.append({
                    "temp": temp,
                    "energy": round(bucket.total_energy_kwh, 2),
                })
        return {"data": data}
