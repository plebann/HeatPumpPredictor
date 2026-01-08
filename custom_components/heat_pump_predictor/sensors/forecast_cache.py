"""Forecast cache sensor."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from ..coordinator import HeatPumpCoordinator
from ..shared_base import HeatPumpBaseEntity

_LOGGER = logging.getLogger(__name__)


class HeatPumpForecastSensor(HeatPumpBaseEntity, SensorEntity):
    """Sensor that caches hourly weather forecast for downstream calculations."""

    _attr_should_poll = False
    _attr_icon = "mdi:weather-partly-cloudy"
    _attr_native_unit_of_measurement = "entries"

    def __init__(self, hass: HomeAssistant, coordinator: HeatPumpCoordinator, weather_entity: str) -> None:
        super().__init__(coordinator, unique_id="hourly_forecast", translation_key="hourly_forecast_cache")
        self.hass = hass
        self._weather_entity = weather_entity
        self._forecast: list[dict[str, Any]] = []
        self._unsub_refresh = None
        self._attr_suggested_object_id = "hourly_forecast_cache"

    async def async_added_to_hass(self) -> None:
        await self._async_update_forecast()
        self._unsub_refresh = async_track_time_interval(
            self.hass, self._handle_refresh, timedelta(minutes=30)
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_refresh:
            self._unsub_refresh()
            self._unsub_refresh = None

    async def _handle_refresh(self, _now) -> None:
        await self._async_update_forecast()

    async def _async_update_forecast(self) -> None:
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
                entity_block = response.get(self._weather_entity) or {}
                forecast = entity_block.get("forecast") or entity_block.get("data") or []
            if not isinstance(forecast, list):
                forecast = []

            self._forecast = forecast
            self.coordinator.hourly_forecast = self._forecast
            self._attr_native_value = len(self._forecast)
            self.async_write_ha_state()
        except Exception as err:  # pylint: disable=broad-except
            # Leave last cached forecast to avoid breaking dependent services.
            self._attr_available = False
            self.async_write_ha_state()
            _LOGGER.warning("Failed to update hourly forecast cache: %s", err)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "forecast": self._forecast,
            "last_updated": dt_util.utcnow().isoformat(),
            "weather_entity": self._weather_entity,
        }