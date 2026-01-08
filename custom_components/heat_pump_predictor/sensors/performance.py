"""Performance curve sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity

from ..const import MAX_TEMP, MIN_TEMP
from ..coordinator import HeatPumpCoordinator
from ..shared_base import HeatPumpBaseEntity


class HeatPumpPerformanceCurveSensor(HeatPumpBaseEntity, SensorEntity):
    """Sensor providing chart-ready performance curve data."""

    _attr_icon = "mdi:chart-bell-curve"

    def __init__(self, coordinator: HeatPumpCoordinator, key: str, name: str) -> None:
        super().__init__(coordinator, unique_id=key)
        self._attr_name = name
        self._key = key
        self._attr_suggested_object_id = key

    @property
    def native_value(self) -> str:
        return "ok"

    @property
    def extra_state_attributes(self) -> dict:
        if self._key == "power_curve":
            return self._get_power_curve_data()
        if self._key == "duty_cycle_curve":
            return self._get_duty_cycle_curve_data()
        if self._key == "energy_distribution":
            return self._get_energy_distribution_data()
        return {}

    def _get_power_curve_data(self) -> dict:
        data = []
        for temp in range(MIN_TEMP, MAX_TEMP + 1):
            bucket = self.coordinator.data_manager.buckets.get(temp)
            if bucket and bucket.total_time_seconds > 0:
                data.append(
                    {
                        "temp": temp,
                        "power_overall": round(bucket.average_power_overall, 1),
                        "power_running": round(bucket.average_power_when_running, 1),
                    }
                )
        return {"data": data}

    def _get_duty_cycle_curve_data(self) -> dict:
        data = []
        for temp in range(MIN_TEMP, MAX_TEMP + 1):
            bucket = self.coordinator.data_manager.buckets.get(temp)
            if bucket and bucket.total_time_seconds > 0:
                data.append({"temp": temp, "duty_cycle": round(bucket.duty_cycle_percent, 2)})
        return {"data": data}

    def _get_energy_distribution_data(self) -> dict:
        data = []
        for temp in range(MIN_TEMP, MAX_TEMP + 1):
            bucket = self.coordinator.data_manager.buckets.get(temp)
            if bucket and bucket.total_energy_kwh > 0:
                data.append({"temp": temp, "energy": round(bucket.total_energy_kwh, 2)})
        return {"data": data}