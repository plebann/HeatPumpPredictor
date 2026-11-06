import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.heat_pump_predictor.forecast_validation import (
    ForecastValidationManager,
    horizon_range,
    normalize_forecast_entries,
    snapshot_hash,
)
from custom_components.heat_pump_predictor.coordinator import HeatPumpCoordinator


FETCHED = datetime(2026, 1, 1, 10, 15, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("hours", "expected"),
    [
        (0.1, "0_3h"),
        (2.99, "0_3h"),
        (3, "3_6h"),
        (6, "6_12h"),
        (12, "12_24h"),
        (24, "24_48h"),
        (48, None),
    ],
)
def test_horizon_ranges_are_half_open(hours: float, expected: str | None) -> None:
    assert horizon_range(hours) == expected


def test_normalization_filters_invalid_entries_and_is_sorted() -> None:
    forecast = [
        {"datetime": "2026-01-02T00:00:00Z", "temperature": "2.5"},
        {"datetime": "2026-01-01T11:00:00+00:00", "temperature": 1},
        {"datetime": "2026-01-01T12:30:00+00:00", "temperature": 2},
        {"datetime": "2026-01-01T13:00:00+00:00", "temperature": "nan"},
        {"datetime": "2026-01-03T10:00:00+00:00", "temperature": 4},
    ]
    assert normalize_forecast_entries(forecast, FETCHED) == [
        ["2026-01-01T11:00:00+00:00", 1.0],
        ["2026-01-02T00:00:00+00:00", 2.5],
        ["2026-01-03T10:00:00+00:00", 4.0],
    ]


def test_snapshot_hash_is_order_independent() -> None:
    first = [
        ["2026-01-01T11:00:00+00:00", 1.0],
        ["2026-01-01T12:00:00+00:00", 2.0],
    ]
    second = list(reversed(first))
    assert snapshot_hash("weather.home", first) == snapshot_hash("weather.home", second)


def test_capture_deduplicates_content_and_appends_fetch_time() -> None:
    store = Mock()
    store.async_load = AsyncMock(return_value=None)
    with patch("custom_components.heat_pump_predictor.forecast_validation.Store", return_value=store):
        manager = ForecastValidationManager(Mock(), "entry")
        forecast = [{"datetime": "2026-01-01T12:00:00Z", "temperature": 2}]
        asyncio.run(manager.async_capture("weather.home", forecast, FETCHED))
        asyncio.run(
            manager.async_capture("weather.home", forecast, FETCHED + timedelta(minutes=1))
        )

    snapshots = manager.data["snapshots"]
    assert len(snapshots) == 1
    assert len(next(iter(snapshots.values()))["fetched_at"]) == 2
    assert store.async_delay_save.call_count == 2


def test_capture_prunes_old_fetches() -> None:
    store = Mock()
    store.async_save = AsyncMock()
    with patch("custom_components.heat_pump_predictor.forecast_validation.Store", return_value=store):
        manager = ForecastValidationManager(Mock(), "entry")
        asyncio.run(
            manager.async_capture(
                "weather.home",
                [{"datetime": "2026-01-01T12:00:00Z", "temperature": 2}],
                FETCHED,
            )
        )
        assert manager.data["snapshots"]
        asyncio.run(manager.async_prune(FETCHED + timedelta(days=29)))
    assert manager.data["snapshots"] == {}


def test_load_ignores_damaged_store() -> None:
    store = Mock()
    store.async_load = AsyncMock(return_value={"unexpected": "shape"})
    with patch("custom_components.heat_pump_predictor.forecast_validation.Store", return_value=store):
        manager = ForecastValidationManager(Mock(), "entry")
        asyncio.run(manager.async_load())
    assert manager.data == {"snapshots": {}, "results": {}}


def test_load_drops_malformed_snapshot_and_allows_future_capture() -> None:
    store = Mock()
    store.async_load = AsyncMock(
        return_value={
            "snapshots": {"broken": None},
            "results": {},
        }
    )
    with patch("custom_components.heat_pump_predictor.forecast_validation.Store", return_value=store):
        manager = ForecastValidationManager(Mock(), "entry")
        asyncio.run(manager.async_load())
        asyncio.run(
            manager.async_capture(
                "weather.home",
                [{"datetime": "2026-01-01T12:00:00Z", "temperature": 2}],
                FETCHED,
            )
        )
    assert len(manager.data["snapshots"]) == 1


def test_capture_store_failure_does_not_change_forecast_cache() -> None:
    class Services:
        async def async_call(self, *args, **kwargs):
            return {"weather.home": {"forecast": [{"temperature": 4}]}}

    class BrokenCapture:
        async def async_capture(self, *args, **kwargs):
            raise OSError("storage unavailable")

    coordinator = object.__new__(HeatPumpCoordinator)
    coordinator.hass = SimpleNamespace(services=Services())
    coordinator.forecast_validation = BrokenCapture()
    coordinator._forecast = None
    coordinator.async_set_updated_data = lambda data: None
    coordinator._build_coordinator_data = lambda: {"forecast": coordinator._forecast}

    forecast = asyncio.run(coordinator.async_refresh_forecast("weather.home"))

    assert forecast == [{"temperature": 4}]
    assert coordinator.forecast == forecast
