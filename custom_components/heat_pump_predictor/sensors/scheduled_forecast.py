"""Scheduled forecast energy sensors."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.event import async_track_time_change

from ..const import CONF_TEMPERATURE_SENSOR, DOMAIN
from ..shared_base import HeatPumpBaseEntity

_LOGGER = logging.getLogger(__name__)


class ScheduledForecastEnergySensor(HeatPumpBaseEntity, SensorEntity):
    """Sensor that stores forecast energy for a fixed daily window."""

    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = "kWh"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:lightning-bolt"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator,
        *,
        unique_id: str,
        translation_key: str,
        schedule_hour: int,
        schedule_minute: int,
        schedule_second: int,
        starting_hour: int,
        hours_ahead: int,
    ) -> None:
        """Initialize the scheduled forecast sensor."""

        super().__init__(coordinator, unique_id=unique_id, translation_key=translation_key)
        self.hass = hass
        self._schedule_hour = schedule_hour
        self._schedule_minute = schedule_minute
        self._schedule_second = schedule_second
        self._starting_hour = starting_hour
        self._hours_ahead = hours_ahead
        self._unsub_time = None
        self._last_attributes: dict[str, Any] = {
            "starting_hour": starting_hour,
            "hours_ahead": hours_ahead,
            "hours": [],
        }
        self._attr_suggested_object_id = unique_id

    async def async_added_to_hass(self) -> None:
        """Register schedule and perform initial calculation."""

        await self._async_update_forecast_energy()

        @callback
        async def _handle_time(_now) -> None:
            await self._async_update_forecast_energy()

        self._unsub_time = async_track_time_change(
            self.hass,
            _handle_time,
            hour=self._schedule_hour,
            minute=self._schedule_minute,
            second=self._schedule_second,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Clean up scheduled callbacks."""

        if self._unsub_time:
            self._unsub_time()
            self._unsub_time = None

    async def _async_update_forecast_energy(self) -> None:
        """Call forecast energy service and update state."""

        try:
            response = await self.coordinator.async_calculate_forecast_energy(
                starting_hour=self._starting_hour,
                hours_ahead=self._hours_ahead,
                current_temperature=self._get_current_temperature(),
            )

            self._attr_available = True
            self._attr_native_value = response.get("total_energy_kwh")
            self._last_attributes = response
            self.async_write_ha_state()
        except ServiceValidationError as err:
            self._attr_available = False
            _LOGGER.warning("Scheduled forecast update failed validation: %s", err)
            self.async_write_ha_state()
        except Exception as err:  # pylint: disable=broad-except
            self._attr_available = False
            _LOGGER.warning("Scheduled forecast update failed: %s", err)
            self.async_write_ha_state()

    def _get_current_temperature(self) -> float | None:
        """Best-effort current temperature for trend adjustment seed."""
        temp_entity = self.coordinator.config_entry.data.get(CONF_TEMPERATURE_SENSOR)
        if not temp_entity:
            return None

        state = self.hass.states.get(temp_entity)
        if state is None:
            return None

        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._last_attributes