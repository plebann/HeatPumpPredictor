"""Coordinator for Heat Pump Predictor integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, Event, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, UPDATE_INTERVAL, CONF_ENERGY_SENSOR, CONF_RUNNING_SENSOR, CONF_TEMPERATURE_SENSOR
from .data_manager import HeatPumpDataManager, TemperatureBucketData

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = "heat_pump_predictor"

class HeatPumpCoordinator(DataUpdateCoordinator[dict[int, TemperatureBucketData]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.config_entry = entry
        self.data_manager = HeatPumpDataManager()
        self._energy_entity = entry.data[CONF_ENERGY_SENSOR]
        self._running_entity = entry.data[CONF_RUNNING_SENSOR]
        self._temperature_entity = entry.data[CONF_TEMPERATURE_SENSOR]
        self._unsub_state_listener = None
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry.entry_id}")
        
        # Create device info
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Heat Pump Predictor",
            manufacturer="Heat Pump Predictor",
            model="Analytics",
            entry_type=None,
        )

    async def _async_update_data(self) -> dict[int, TemperatureBucketData]:
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
            return self.data_manager.buckets
        except Exception as err:
            raise UpdateFailed(f"Error: {err}") from err

    async def async_setup(self) -> None:
        # Load saved data before first refresh
        if data := await self._store.async_load():
            self.data_manager.from_dict(data.get("buckets", {}))
            _LOGGER.info("Loaded saved heat pump data from storage")
        
        await self.async_config_entry_first_refresh()
        self._unsub_state_listener = async_track_state_change_event(
            self.hass, [self._energy_entity, self._running_entity, self._temperature_entity], self._handle_state_change
        )

    async def async_shutdown(self) -> None:
        # Save data before shutdown
        await self._save_data()
        _LOGGER.info("Saved heat pump data to storage")
        
        if self._unsub_state_listener:
            self._unsub_state_listener()
    
    async def _save_data(self) -> None:
        """Save bucket data to storage."""
        try:
            await self._store.async_save({"buckets": self.data_manager.to_dict()})
        except Exception as err:
            _LOGGER.error("Failed to save data to storage: %s", err)

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
            self.async_set_updated_data(self.data_manager.buckets)
        except (ValueError, TypeError):
            pass
