"""Coordinator for Heat Pump Predictor integration."""
from __future__ import annotations

import logging
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, Event, State, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .calculator import HeatPumpCalculator
from .const import DOMAIN, UPDATE_INTERVAL, CONF_ENERGY_SENSOR, CONF_RUNNING_SENSOR, CONF_TEMPERATURE_SENSOR
from .data_manager import HeatPumpDataManager
from .forecast_energy import ForecastEnergyCalculationError, ForecastEnergyCalculator

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = "heat_pump_predictor"
FORECAST_ENERGY_TRANSLATION_KEYS = {
    "forecast_window_too_small": "forecast_window_too_small",
    "forecast_hour_missing": "forecast_hour_missing",
    "no_data_for_approximation": "no_data_for_approximation",
}
UNAVAILABLE_SOURCE_STATES = {STATE_UNAVAILABLE, STATE_UNKNOWN}


def _state_float_value(state: State) -> float | None:
    """Return a float for a numeric HA state, or None if it is temporarily unavailable."""
    if state.state in UNAVAILABLE_SOURCE_STATES:
        return None
    return float(state.state)


def _running_state_value(state: State) -> bool | None:
    """Return a binary sensor value, or None if it is temporarily unavailable."""
    if state.state in UNAVAILABLE_SOURCE_STATES:
        return None
    if state.state == STATE_ON:
        return True
    if state.state == STATE_OFF:
        return False
    return None


class HeatPumpCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.config_entry = entry
        self.data_manager = HeatPumpDataManager()
        self.calculator = HeatPumpCalculator(self.data_manager)
        self.forecast_energy_calculator = ForecastEnergyCalculator(self.calculator)
        self._energy_entity = entry.data[CONF_ENERGY_SENSOR]
        self._running_entity = entry.data[CONF_RUNNING_SENSOR]
        self._temperature_entity = entry.data[CONF_TEMPERATURE_SENSOR]
        self._unsub_state_listener: Callable[[], None] | None = None
        self._unsub_stop_listener: Callable[[], None] | None = None
        self._shutdown = False
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry.entry_id}")
        self._save_debounce_seconds = 5
        self._forecast: list[dict[str, Any]] | None = None
        self._bucket_observed_callbacks: list[Callable[[int], None]] = []

        # Create device info
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Heat Pump Predictor",
            model="Analytics",
            entry_type=None,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            energy_state = self.hass.states.get(self._energy_entity)
            running_state = self.hass.states.get(self._running_entity)
            temp_state = self.hass.states.get(self._temperature_entity)
            if not all([energy_state, running_state, temp_state]):
                raise UpdateFailed("Sensors unavailable")
            current_energy = _state_float_value(energy_state)
            current_temp = _state_float_value(temp_state)
            is_running = _running_state_value(running_state)
            if current_energy is None or current_temp is None or is_running is None:
                _LOGGER.debug(
                    "Skipping heat pump update because one or more source sensors are unavailable"
                )
                return self._build_coordinator_data()
            new_bucket_temp = self.data_manager.process_state_update(
                current_temp, current_energy, is_running, dt_util.utcnow()
            )
            self._notify_bucket_observed(new_bucket_temp)
            await self._save_data()
            return self._build_coordinator_data()
        except Exception as err:
            raise UpdateFailed(f"Error: {err}") from err

    async def async_setup(self) -> None:
        # Load saved data before first refresh
        if data := await self._store.async_load():
            self.data_manager.from_dict(data)
            _LOGGER.info("Loaded saved heat pump data from storage")

        await self.async_config_entry_first_refresh()
        self._unsub_state_listener = async_track_state_change_event(
            self.hass, [self._energy_entity, self._running_entity, self._temperature_entity], self._handle_state_change
        )
        self._unsub_stop_listener = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self._handle_hass_stop
        )

    async def async_shutdown(self) -> None:
        # Save data before shutdown
        if self._shutdown:
            return
        self._shutdown = True

        await self._save_data()
        _LOGGER.info("Saved heat pump data to storage")

        self._async_unsubscribe_state_listener()
        self._async_unsubscribe_stop_listener()

    def _async_unsubscribe_state_listener(self) -> None:
        """Safely remove state change listener."""
        if not self._unsub_state_listener:
            return
        try:
            self._unsub_state_listener()
        except ValueError:
            _LOGGER.debug("State listener already removed during shutdown", exc_info=True)
        self._unsub_state_listener = None

    def _async_unsubscribe_stop_listener(self) -> None:
        """Safely remove HA stop listener."""
        if not self._unsub_stop_listener:
            return
        try:
            self._unsub_stop_listener()
        except ValueError:
            _LOGGER.debug("Stop listener already removed during shutdown", exc_info=True)
        self._unsub_stop_listener = None

    async def _save_data(self) -> None:
        """Save bucket data to storage."""
        try:
            _LOGGER.debug("Saving heat pump data to storage")
            await self._store.async_save(self.data_manager.to_dict())
        except Exception as err:
            _LOGGER.error("Failed to save data to storage: %s", err)

    @callback
    def _schedule_debounced_save(self) -> None:
        """Schedule a debounced save to storage."""
        self._store.async_delay_save(self.data_manager.to_dict, self._save_debounce_seconds)

    @callback
    def async_register_bucket_observed_callback(self, callback_fn: Callable[[int], None]) -> Callable[[], None]:
        """Register a callback for newly observed temperature buckets."""
        self._bucket_observed_callbacks.append(callback_fn)

        @callback
        def _unsubscribe() -> None:
            if callback_fn in self._bucket_observed_callbacks:
                self._bucket_observed_callbacks.remove(callback_fn)

        return _unsubscribe

    @callback
    def _notify_bucket_observed(self, bucket_temp: int | None) -> None:
        """Notify listeners that a temperature bucket first received observed time."""
        if bucket_temp is None:
            return
        for callback_fn in list(self._bucket_observed_callbacks):
            callback_fn(bucket_temp)

    async def _handle_hass_stop(self, event: Event) -> None:
        """Handle Home Assistant stop to flush data."""
        await self._save_data()

    @callback
    def _handle_state_change(self, event: Event) -> None:
        energy_state = self.hass.states.get(self._energy_entity)
        running_state = self.hass.states.get(self._running_entity)
        temp_state = self.hass.states.get(self._temperature_entity)
        if not all([energy_state, running_state, temp_state]):
            return
        try:
            current_energy = _state_float_value(energy_state)
            current_temp = _state_float_value(temp_state)
            is_running = _running_state_value(running_state)
            if current_energy is None or current_temp is None or is_running is None:
                return
            new_bucket_temp = self.data_manager.process_state_update(
                current_temp, current_energy, is_running, dt_util.utcnow()
            )
            self._notify_bucket_observed(new_bucket_temp)
            # Update coordinator data without cancelling the scheduled refresh
            self.async_set_updated_data(self._build_coordinator_data())
            self.last_update_success = True
            self.async_update_listeners()
            self._schedule_debounced_save()
        except (ValueError, TypeError) as err:
            _LOGGER.debug("Ignoring invalid heat pump sensor state update: %s", err)

    async def async_refresh_forecast(self, weather_entity: str) -> list[dict[str, Any]]:
        """Fetch and cache hourly forecast for downstream calculations."""

        response = await self.hass.services.async_call(
            "weather",
            "get_forecasts",
            {"entity_id": weather_entity, "type": "hourly"},
            blocking=True,
            return_response=True,
        )

        forecast: list[dict[str, Any]] = []
        if isinstance(response, dict):
            entity_block = response.get(weather_entity) or {}
            forecast = entity_block.get("forecast") or entity_block.get("data") or []
        if not isinstance(forecast, list):
            forecast = []

        self._forecast = forecast
        self.async_set_updated_data(self._build_coordinator_data())
        return forecast

    async def async_calculate_forecast_energy(
        self,
        *,
        starting_hour: int,
        hours_ahead: int,
        current_temperature: float | None,
    ) -> dict[str, Any]:
        """Calculate energy consumption for a forecast window using cached forecast data."""

        if not self._forecast:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="forecast_unavailable",
            )

        try:
            result = self.forecast_energy_calculator.calculate(
                self._forecast,
                starting_hour=starting_hour,
                hours_ahead=hours_ahead,
                current_temperature=current_temperature,
                now=dt_util.as_local(dt_util.utcnow()),
            )
        except ForecastEnergyCalculationError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=FORECAST_ENERGY_TRANSLATION_KEYS[err.reason_key],
                translation_placeholders=err.placeholders,
            ) from err

        return result.as_response()

    @property
    def forecast(self) -> list[dict[str, Any]] | None:
        """Return cached forecast data, if any."""
        return self._forecast

    def _build_coordinator_data(self) -> dict[str, Any]:
        """Compose coordinator data payload for listeners."""
        return {
            "buckets": self.data_manager.buckets,
            "forecast": self._forecast,
        }
