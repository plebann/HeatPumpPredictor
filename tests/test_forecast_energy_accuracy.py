from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
import asyncio
import pytest

from custom_components.heat_pump_predictor.forecast_validation import (
    ForecastValidationManager,
    energy_horizon_bucket,
    energy_window_actual,
)


UTC = timezone.utc


def state(at: datetime, value: str) -> dict[str, object]:
    return {"last_changed": at, "state": value}


def test_energy_window_uses_exclusive_end_and_detects_reset() -> None:
    start = datetime(2026, 1, 1, 10, tzinfo=UTC)
    end = start + timedelta(hours=1)
    states = [
        state(start, "10.00"),
        state(start + timedelta(minutes=20), "10.10"),
        state(start + timedelta(minutes=40), "9.00"),
        state(end, "10.20"),
    ]

    actual, reason = energy_window_actual(states, start, end)

    assert actual is None
    assert reason == "negative_difference"


def test_energy_window_returns_cumulative_difference_at_boundaries() -> None:
    start = datetime(2026, 1, 1, 10, tzinfo=UTC)
    end = start + timedelta(hours=1)
    states = [state(start - timedelta(minutes=1), "10.00"), state(end, "10.25")]

    assert energy_window_actual(states, start, end) == (0.25, None)


def test_energy_horizon_rounds_up_into_product_buckets() -> None:
    assert energy_horizon_bucket(3.0) == "0_3h"
    assert energy_horizon_bucket(3.01) == "4_6h"
    assert energy_horizon_bucket(24.01) == "over_24h"


def test_recording_uses_last_hour_as_exclusive_window_end() -> None:
    store = Mock()
    store.async_delay_save = Mock()
    with patch(
        "custom_components.heat_pump_predictor.forecast_validation.Store",
        return_value=store,
    ):
        manager = ForecastValidationManager(
            Mock(), "entry", energy_entity="sensor.heat_pump_energy"
        )
    first = datetime(2026, 1, 1, 10, tzinfo=UTC)
    result = SimpleNamespace(
        total_energy_kwh=1.23456,
        hours=[
            SimpleNamespace(datetime=first),
            SimpleNamespace(datetime=first + timedelta(hours=1)),
        ],
    )

    asyncio.run(manager.async_record_energy_forecast(first - timedelta(hours=2), result))

    observation = next(iter(manager.data["energy_observations"].values()))
    assert observation["window_start"] == first.isoformat()
    assert observation["window_end"] == (first + timedelta(hours=2)).isoformat()
    assert observation["predicted_kwh"] == 1.23456


def test_energy_accuracy_requires_three_samples_and_exposes_recent_average() -> None:
    store = Mock()
    with patch(
        "custom_components.heat_pump_predictor.forecast_validation.Store",
        return_value=store,
    ):
        manager = ForecastValidationManager(
            Mock(), "entry", energy_entity="sensor.heat_pump_energy"
        )
    start = datetime(2026, 1, 1, tzinfo=UTC)
    manager.data["energy_results"] = {
        str(index): {
            "status": "validated",
            "energy_entity": "sensor.heat_pump_energy",
            "window_end": (start + timedelta(days=index)).isoformat(),
            "predicted_kwh": predicted,
            "actual_kwh": actual,
            "accuracy_percent": accuracy,
            "horizon_bucket": "0_3h",
        }
        for index, (predicted, actual, accuracy) in enumerate(
            [(1.0, 1.0, 100.0), (2.0, 1.0, 200.0), (1.0, 2.0, 50.0)]
        )
    }

    diagnostics = manager.energy_accuracy(start + timedelta(days=3))

    assert diagnostics["accuracy"] == pytest.approx(97.46981099)
    assert diagnostics["samples"] == 3
    assert diagnostics["recent_accuracy"] == (100.0 + 200.0 + 50.0) / 3
