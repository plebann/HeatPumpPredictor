"""Coordinator for Heat Pump Predictor integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, Event, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .calculator import HeatPumpCalculator
from .const import DOMAIN, UPDATE_INTERVAL, CONF_ENERGY_SENSOR, CONF_RUNNING_SENSOR, CONF_TEMPERATURE_SENSOR
from .data_manager import HeatPumpDataManager, TemperatureBucketData

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = "heat_pump_predictor"

class HeatPumpCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.config_entry = entry
        self.data_manager = HeatPumpDataManager()
        self.calculator = HeatPumpCalculator(self.data_manager)
        self._energy_entity = entry.data[CONF_ENERGY_SENSOR]
        self._running_entity = entry.data[CONF_RUNNING_SENSOR]
        self._temperature_entity = entry.data[CONF_TEMPERATURE_SENSOR]
        self._unsub_state_listener: Callable[[], None] | None = None
        self._unsub_stop_listener: Callable[[], None] | None = None
        self._shutdown = False
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry.entry_id}")
        self._save_debounce_seconds = 5
        self._forecast: list[dict[str, Any]] | None = None
        
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
            current_energy = float(energy_state.state)
            current_temp = float(temp_state.state)
            is_running = running_state.state == "on"
            self.data_manager.process_state_update(current_temp, current_energy, is_running, dt_util.utcnow())
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
            self.data_manager.process_state_update(
                float(temp_state.state), float(energy_state.state), running_state.state == "on", dt_util.utcnow()
            )
            # Update coordinator data without cancelling the scheduled refresh
            self.async_set_updated_data(self._build_coordinator_data())
            self.last_update_success = True
            self.async_update_listeners()
            self._schedule_debounced_save()
        except (ValueError, TypeError):
            pass

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

        now_local = dt_util.as_local(dt_util.utcnow())
        parsed_forecast: list[tuple[Any, dict[str, Any]]] = []
        for item in self._forecast:
            dt_val = dt_util.parse_datetime(item.get("datetime")) if isinstance(item, dict) else None
            if dt_val is None:
                continue
            parsed_forecast.append((dt_util.as_local(dt_val), item))

        parsed_forecast.sort(key=lambda pair: pair[0])

        start_indexes = [idx for idx, (dt_val, _) in enumerate(parsed_forecast) if dt_val >= now_local and dt_val.hour == starting_hour]
        if not start_indexes:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="forecast_window_too_small",
            )

        start_index = start_indexes[0]
        window = parsed_forecast[start_index : start_index + hours_ahead]

        if len(window) < hours_ahead:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="forecast_window_too_small",
            )

        total_energy_kwh = 0.0
        hour_details: list[dict[str, Any]] = []
        approximated_hours = 0

        window_start_dt = parsed_forecast[start_index][0]
        next_hour_start = now_local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

        if window_start_dt == next_hour_start:
            previous_temp: float | None = current_temperature
        else:
            if start_index == 0:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="forecast_window_too_small",
                )

            prev_dt, prev_payload = parsed_forecast[start_index - 1]
            prev_temp_raw = prev_payload.get("temperature") if isinstance(prev_payload, dict) else None
            if prev_temp_raw is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="forecast_hour_missing",
                    translation_placeholders={"datetime": prev_dt.isoformat()},
                )

            try:
                previous_temp = float(prev_temp_raw)
            except (TypeError, ValueError) as err:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="forecast_hour_missing",
                    translation_placeholders={"datetime": prev_dt.isoformat()},
                ) from err

        for dt_val, payload in window:
            temperature = payload.get("temperature") if isinstance(payload, dict) else None
            if temperature is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="forecast_hour_missing",
                    translation_placeholders={"datetime": dt_val.isoformat()},
                )

            temp_float = float(temperature)
            try:
                estimation = self.calculator.interpolate_estimation(temp_float)
            except ValueError as err:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="no_data_for_approximation",
                    translation_placeholders={"temperature": str(temp_float)},
                ) from err

            delta = None
            if previous_temp is not None:
                delta = temp_float - previous_temp

            energy_kwh = estimation["power_overall_w"] / 1000.0
            if delta is not None:
                energy_kwh *= self.calculator.trend_adjustment(delta)

            total_energy_kwh += energy_kwh
            approximated_hours += 1 if estimation["approximated"] else 0

            hour_details.append(
                {
                    "datetime": dt_val.isoformat(),
                    "temperature": temp_float,
                    "temperature_delta": delta,
                    "trend_adjustment": None if delta is None else self.calculator.trend_adjustment(delta),
                    "energy_kwh": round(energy_kwh, 3),
                    "confidence": estimation["confidence"],
                    "approximated": estimation["approximated"],
                    "approximation_source": estimation.get("approximation_source"),
                }
            )

            previous_temp = temp_float

        return {
            "total_energy_kwh": round(total_energy_kwh, 3),
            "hours": hour_details,
            "hours_requested": hours_ahead,
            "hours_returned": len(hour_details),
            "approximated_hours": approximated_hours,
            "starting_hour": starting_hour,
        }

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
