"""Tests for calculator behavior with dynamic temperature buckets."""
from __future__ import annotations

from custom_components.heat_pump_predictor.calculator import HeatPumpCalculator
from custom_components.heat_pump_predictor.data_manager import HeatPumpDataManager, TemperatureBucketData


def _add_observed_bucket(
    manager: HeatPumpDataManager,
    temperature: int,
    *,
    energy_kwh: float,
    total_hours: float,
    running_hours: float,
) -> None:
    manager.buckets[temperature] = TemperatureBucketData(
        temperature=temperature,
        total_energy_kwh=energy_kwh,
        total_time_seconds=total_hours * 3600,
        running_time_seconds=running_hours * 3600,
        last_update=None,
    )


def test_estimation_uses_nearest_observed_bucket_without_creating_requested_bucket() -> None:
    """Approximate from dynamic observed buckets outside the old fixed range."""
    manager = HeatPumpDataManager()
    _add_observed_bucket(manager, -40, energy_kwh=2.0, total_hours=1.0, running_hours=1.0)
    _add_observed_bucket(manager, 40, energy_kwh=1.0, total_hours=1.0, running_hours=1.0)

    estimation = HeatPumpCalculator(manager).estimate_power_for_temperature(48.2)

    assert estimation["temperature_bucket"] == 48
    assert estimation["approximated"] is True
    assert estimation["confidence"] == "approximated"
    assert estimation["approximation_source"] == 40
    assert 48 not in manager.buckets


def test_interpolation_uses_dynamic_floor_and_ceiling_without_clamping() -> None:
    """Interpolate between observed buckets above the old fixed range."""
    manager = HeatPumpDataManager()
    _add_observed_bucket(manager, 40, energy_kwh=1.0, total_hours=1.0, running_hours=1.0)
    _add_observed_bucket(manager, 41, energy_kwh=2.0, total_hours=1.0, running_hours=1.0)

    estimation = HeatPumpCalculator(manager).interpolate_estimation(40.5)

    assert estimation["temperature_bucket"] == 40.5
    assert estimation["power_overall_w"] == 1500.0
    assert estimation["power_running_w"] == 1500.0
    assert estimation["approximated"] is False
    assert 40.5 not in manager.buckets
