"""Tests for dynamic temperature bucket observation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.heat_pump_predictor.data_manager import HeatPumpDataManager


def test_observed_temperature_bucket_is_created_without_clamping() -> None:
    """Attribute observed time to the actual previous temperature bucket."""
    manager = HeatPumpDataManager()
    start = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)

    manager.process_state_update(-30.2, 100.0, True, start)
    new_bucket = manager.process_state_update(-29.8, 101.5, True, start + timedelta(hours=1))

    bucket = manager.buckets[-31]
    assert new_bucket == -31
    assert bucket.temperature == -31
    assert bucket.total_time_seconds == pytest.approx(3600)
    assert bucket.running_time_seconds == pytest.approx(3600)
    assert bucket.total_energy_kwh == pytest.approx(1.5)
    assert -25 not in manager.observed_bucket_temperatures


def test_existing_observed_bucket_update_does_not_report_new_bucket() -> None:
    """Report a bucket only when it first receives observed time."""
    manager = HeatPumpDataManager()
    start = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)

    manager.process_state_update(10.2, 100.0, True, start)
    first_bucket = manager.process_state_update(10.4, 101.0, True, start + timedelta(hours=1))
    second_bucket = manager.process_state_update(10.6, 102.0, True, start + timedelta(hours=2))

    assert first_bucket == 10
    assert second_bucket is None


def test_single_temperature_reading_does_not_create_observed_bucket() -> None:
    """Keep instantaneous readings out of the observed bucket span."""
    manager = HeatPumpDataManager()

    manager.process_state_update(44.9, 10.0, False, datetime(2026, 1, 1, tzinfo=timezone.utc))

    assert manager.buckets == {}
    assert manager.observed_bucket_temperatures == []


def test_restored_empty_legacy_buckets_are_not_observed() -> None:
    """Ignore empty restored buckets when enumerating observed history."""
    manager = HeatPumpDataManager()

    manager.from_dict(
        {
            "buckets": {
                "-25": {
                    "temperature": -25,
                    "total_energy_kwh": 0.0,
                    "total_time_seconds": 0.0,
                    "running_time_seconds": 0.0,
                    "last_update": None,
                },
                "12": {
                    "temperature": 12,
                    "total_energy_kwh": 2.0,
                    "total_time_seconds": 7200.0,
                    "running_time_seconds": 3600.0,
                    "last_update": None,
                },
            }
        }
    )

    assert manager.observed_bucket_temperatures == [12]
    assert manager.observed_temperature_span == (12, 12)


def test_service_prediction_range_extends_observed_span_by_five_degrees() -> None:
    """Expose the inclusive manual service range from observed history."""
    manager = HeatPumpDataManager()
    manager.buckets[-12] = manager.get_or_create_bucket(-12.0)
    manager.buckets[-12].total_time_seconds = 1800.0
    manager.buckets[18] = manager.get_or_create_bucket(18.0)
    manager.buckets[18].total_time_seconds = 3600.0

    assert manager.service_prediction_range == (-17, 23)
    assert manager.is_within_service_prediction_range(-17.0) is True
    assert manager.is_within_service_prediction_range(23.0) is True
    assert manager.is_within_service_prediction_range(-17.1) is False
    assert manager.is_within_service_prediction_range(23.1) is False


def test_service_prediction_range_is_unavailable_without_observed_time() -> None:
    """Do not expose a manual service range before useful history exists."""
    manager = HeatPumpDataManager()

    assert manager.service_prediction_range is None
    assert manager.is_within_service_prediction_range(10.0) is False
