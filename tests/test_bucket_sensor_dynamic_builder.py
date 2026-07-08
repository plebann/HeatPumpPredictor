"""Tests for dynamic bucket sensor creation."""
from __future__ import annotations

from types import SimpleNamespace

from custom_components.heat_pump_predictor.data_manager import HeatPumpDataManager, TemperatureBucketData
from custom_components.heat_pump_predictor.sensors.buckets import build_bucket_sensors


class _CoordinatorStub:
    """Small coordinator stand-in for constructing sensor entities."""

    def __init__(self) -> None:
        self.config_entry = SimpleNamespace(entry_id="entry-1")
        self.device_info = {"identifiers": {("heat_pump_predictor", "entry-1")}}
        self.last_update_success = True
        self.data_manager = HeatPumpDataManager()

    def async_add_listener(self, *_args, **_kwargs):
        return lambda: None


def _add_bucket(manager: HeatPumpDataManager, temperature: int, total_time_seconds: float) -> None:
    manager.buckets[temperature] = TemperatureBucketData(
        temperature=temperature,
        total_energy_kwh=1.0,
        total_time_seconds=total_time_seconds,
        running_time_seconds=total_time_seconds,
        last_update=None,
    )


def test_bucket_sensors_are_built_only_for_observed_buckets() -> None:
    """Create four per-bucket sensors for each bucket with observed time."""
    coordinator = _CoordinatorStub()
    _add_bucket(coordinator.data_manager, -40, 3600.0)
    _add_bucket(coordinator.data_manager, 12, 0.0)
    _add_bucket(coordinator.data_manager, 44, 1800.0)

    sensors = list(build_bucket_sensors(coordinator))

    assert [sensor.entity_description.bucket_temp for sensor in sensors] == [
        -40,
        -40,
        -40,
        -40,
        44,
        44,
        44,
        44,
    ]
