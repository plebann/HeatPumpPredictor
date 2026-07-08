"""Tests for dynamic performance curve data."""
from __future__ import annotations

from types import SimpleNamespace

from custom_components.heat_pump_predictor.data_manager import HeatPumpDataManager, TemperatureBucketData
from custom_components.heat_pump_predictor.sensors.performance import HeatPumpPerformanceCurveSensor


class _CoordinatorStub:
    """Small coordinator stand-in for constructing performance sensors."""

    def __init__(self) -> None:
        self.config_entry = SimpleNamespace(entry_id="entry-1")
        self.device_info = {"identifiers": {("heat_pump_predictor", "entry-1")}}
        self.last_update_success = True
        self.data_manager = HeatPumpDataManager()

    def async_add_listener(self, *_args, **_kwargs):
        return lambda: None


def _bucket(temperature: int, total_time_seconds: float, energy_kwh: float) -> TemperatureBucketData:
    return TemperatureBucketData(
        temperature=temperature,
        total_energy_kwh=energy_kwh,
        total_time_seconds=total_time_seconds,
        running_time_seconds=total_time_seconds,
        last_update=None,
    )


def test_power_curve_uses_observed_buckets_sorted_by_temperature() -> None:
    """Expose chart data from dynamic observed buckets only."""
    coordinator = _CoordinatorStub()
    coordinator.data_manager.buckets[44] = _bucket(44, 3600.0, 2.0)
    coordinator.data_manager.buckets[-40] = _bucket(-40, 1800.0, 1.0)
    coordinator.data_manager.buckets[12] = _bucket(12, 0.0, 0.0)

    sensor = HeatPumpPerformanceCurveSensor(coordinator, "power_curve", "performance_power_curve")

    assert [item["temp"] for item in sensor.extra_state_attributes["data"]] == [-40, 44]
