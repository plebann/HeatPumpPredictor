"""Sensor platform for Heat Pump Predictor integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Callable, Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    MIN_TEMP,
    MAX_TEMP,
    TRANSLATION_KEY_ENERGY,
    TRANSLATION_KEY_AVG_POWER_RUNNING,
    TRANSLATION_KEY_AVG_POWER_OVERALL,
    TRANSLATION_KEY_DUTY_CYCLE,
    CONF_WEATHER_ENTITY,
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
    weather_entity = entry.data.get(CONF_WEATHER_ENTITY)
    if weather_entity:
        entities.append(
            HeatPumpForecastSensor(
                hass,
                coordinator,
                weather_entity,
            )
        )
    else:
        _LOGGER.error("Weather entity not configured; forecast cache sensor will not be created")
    for temp in range(MIN_TEMP, MAX_TEMP + 1):
        entities.extend([
            HeatPumpSensor(coordinator, HeatPumpSensorEntityDescription(
                key=f"total_energy_{temp}", translation_key=TRANSLATION_KEY_ENERGY, bucket_temp=temp,
                device_class=SensorDeviceClass.ENERGY, native_unit_of_measurement="kWh",
                state_class=SensorStateClass.TOTAL_INCREASING, entity_registry_enabled_default=False,
                icon="mdi:lightning-bolt",
                value_fn=lambda data: data.total_energy_kwh,
            )),
            HeatPumpSensor(coordinator, HeatPumpSensorEntityDescription(
                key=f"avg_power_running_{temp}", translation_key=TRANSLATION_KEY_AVG_POWER_RUNNING, bucket_temp=temp,
                device_class=SensorDeviceClass.POWER, native_unit_of_measurement="W",
                state_class=SensorStateClass.MEASUREMENT, entity_registry_enabled_default=False,
                icon="mdi:flash",
                value_fn=lambda data: data.average_power_when_running,
            )),
            HeatPumpSensor(coordinator, HeatPumpSensorEntityDescription(
                key=f"avg_power_overall_{temp}", translation_key=TRANSLATION_KEY_AVG_POWER_OVERALL, bucket_temp=temp,
                device_class=SensorDeviceClass.POWER, native_unit_of_measurement="W",
                state_class=SensorStateClass.MEASUREMENT, entity_registry_enabled_default=False,
                icon="mdi:flash",
                value_fn=lambda data: data.average_power_overall,
            )),
            HeatPumpSensor(coordinator, HeatPumpSensorEntityDescription(
                key=f"duty_cycle_{temp}", translation_key=TRANSLATION_KEY_DUTY_CYCLE, bucket_temp=temp,
                native_unit_of_measurement="%", state_class=SensorStateClass.MEASUREMENT,
                suggested_display_precision=2, entity_registry_enabled_default=False,
                icon="mdi:percent",
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
        
        # Enforce predictable entity_id
        self.entity_id = f"sensor.heat_pump_predictor_{description.key}"

    @property
    def native_value(self) -> float | None:
        bucket = self.coordinator.data_manager.buckets.get(self.entity_description.bucket_temp)
        if bucket and self.entity_description.value_fn:
            return self.entity_description.value_fn(bucket)
        return None


class HeatPumpPerformanceCurveSensor(CoordinatorEntity[HeatPumpCoordinator], SensorEntity):
    """Sensor providing chart-ready performance curve data."""
    
    _attr_has_entity_name = True
    _attr_icon = "mdi:chart-bell-curve"
    
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


class HeatPumpForecastSensor(SensorEntity):
    """Sensor that caches hourly weather forecast for downstream calculations."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:weather-partly-cloudy"

    def __init__(self, hass: HomeAssistant, coordinator: HeatPumpCoordinator, weather_entity: str) -> None:
        """Initialize the forecast cache sensor."""
        self.hass = hass
        self._coordinator = coordinator
        self._weather_entity = weather_entity
        self._attr_translation_key = "hourly_forecast_cache"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_hourly_forecast"
        self.entity_id = f"sensor.{DOMAIN}_hourly_forecast_{coordinator.config_entry.entry_id}"
        self._attr_native_unit_of_measurement = "entries"
        self._attr_native_value = None
        self._forecast: list[dict[str, Any]] = []
        self._unsub_refresh = None

    async def async_added_to_hass(self) -> None:
        """Handle sensor addition."""
        await self._async_update_forecast()
        self._unsub_refresh = async_track_time_interval(
            self.hass, self._handle_refresh, timedelta(minutes=30)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Clean up callbacks."""
        if self._unsub_refresh:
            self._unsub_refresh()
            self._unsub_refresh = None

    async def _handle_refresh(self, _now) -> None:
        """Periodic refresh handler."""
        await self._async_update_forecast()

    async def _async_update_forecast(self) -> None:
        """Fetch and cache the hourly forecast."""
        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": self._weather_entity, "type": "hourly"},
                blocking=True,
                return_response=True,
            )
            forecast: list[dict[str, Any]] = []
            if isinstance(response, dict):
                forecast = response.get("forecast") or response.get("data") or []
            if not isinstance(forecast, list):
                forecast = []

            self._forecast = forecast
            self._coordinator.hourly_forecast = self._forecast
            self._attr_native_value = len(self._forecast)
            self.async_write_ha_state()
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.warning("Failed to update hourly forecast cache: %s", err)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the cached forecast list."""
        return {
            "forecast": self._forecast,
            "last_updated": dt_util.utcnow().isoformat(),
            "weather_entity": self._weather_entity,
        }
    
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
