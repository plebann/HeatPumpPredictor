"""Diagnostic sensor for forecast temperature validation results."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from ..coordinator import HeatPumpCoordinator
from ..forecast_validation import HORIZON_RANGES, aggregate_diagnostics
from ..shared_base import HeatPumpBaseEntity


class ForecastTemperatureValidationSensor(HeatPumpBaseEntity, SensorEntity):
    """Expose validated forecast-temperature differences for diagnostics."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "windows"
    _attr_should_poll = False
    _attr_icon = "mdi:thermometer-check"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: HeatPumpCoordinator,
        weather_entity: str,
    ) -> None:
        super().__init__(coordinator, "forecast_temperature_validation", "forecast_temperature_validation")
        self.hass = hass
        self._weather_entity = weather_entity
        self._attr_suggested_object_id = f"{DOMAIN}_forecast_temperature_validation"
        self._attr_extra_state_attributes: dict[str, Any] = {}
        self._unsubscribe = coordinator.forecast_validation.async_register_update_callback(
            self._handle_validation_update
        )

    async def async_added_to_hass(self) -> None:
        self._refresh_attributes(dt_util.utcnow())

    async def async_will_remove_from_hass(self) -> None:
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None

    @callback
    def _handle_validation_update(self) -> None:
        self._refresh_attributes(dt_util.utcnow())
        self.async_write_ha_state()

    def _refresh_attributes(self, now: datetime) -> None:
        manager = self.coordinator.forecast_validation
        total, ranges, unvalidated = aggregate_diagnostics(
            manager.data.get("results", {}), now, self._weather_entity
        )
        period_start = now - timedelta(days=14)
        self._attr_native_value = total
        self._attr_extra_state_attributes = {
            "period_start": period_start.isoformat(),
            "period_end": now.isoformat(),
            "weather_entity": self._weather_entity,
            "ranges": {key: ranges[key] for key in HORIZON_RANGES},
            "unvalidated": unvalidated,
            "description": (
                "różnica prognozy punktowej względem średniej godzinnej; "
                "nie jest biasem do korekty"
            ),
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the latest diagnostic aggregates."""
        return self._attr_extra_state_attributes
