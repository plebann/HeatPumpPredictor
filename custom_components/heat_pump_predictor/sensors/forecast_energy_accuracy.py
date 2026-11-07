"""Diagnostic sensor for end-to-end forecast energy accuracy."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from ..coordinator import HeatPumpCoordinator
from ..shared_base import HeatPumpBaseEntity


class ForecastEnergyAccuracySensor(HeatPumpBaseEntity, SensorEntity):
    """Expose energy-weighted forecast accuracy diagnostics."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "%"
    _attr_should_poll = False
    _attr_icon = "mdi:chart-bell-curve-cumulative"
    _attr_translation_key = "forecast_energy_accuracy"

    def __init__(self, hass: HomeAssistant, coordinator: HeatPumpCoordinator) -> None:
        super().__init__(coordinator, "forecast_energy_accuracy", "forecast_energy_accuracy")
        self.hass = hass
        self._attr_suggested_object_id = f"{DOMAIN}_forecast_energy_accuracy"
        self._attr_extra_state_attributes: dict[str, Any] = {}
        self._unsubscribe = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._unsubscribe = self.coordinator.forecast_validation.async_register_update_callback(
            self._handle_update
        )
        self._refresh(dt_util.utcnow())

    async def async_will_remove_from_hass(self) -> None:
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_update(self) -> None:
        self._refresh(dt_util.utcnow())
        self.async_write_ha_state()

    def _refresh(self, now: datetime) -> None:
        diagnostics = self.coordinator.forecast_validation.energy_accuracy(now)
        self._attr_native_value = diagnostics["accuracy"]
        self._attr_extra_state_attributes = {
            "description": (
                "end-to-end accuracy including weather forecast and heat-pump power-curve error"
            ),
            "energy_entity": self.coordinator.energy_entity,
            "period_end": now.isoformat(),
            "half_life_days": diagnostics["half_life_days"],
            "samples": diagnostics["samples"],
            "effective_samples": diagnostics["effective_samples"],
            "recent_accuracy": diagnostics["recent_accuracy"],
            "buckets": diagnostics["buckets"],
            "latest": diagnostics["latest"],
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic details."""
        return self._attr_extra_state_attributes
