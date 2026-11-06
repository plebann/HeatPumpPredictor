from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.heat_pump_predictor.forecast_validation import (
    ForecastValidationManager,
    RecorderHistoryUnavailable,
    aggregate_metrics,
    select_representative_snapshots,
    time_weighted_mean,
)
from custom_components.heat_pump_predictor.coordinator import HeatPumpCoordinator


UTC = timezone.utc
START = datetime(2026, 1, 1, 10, tzinfo=UTC)


def state(value: str, timestamp: datetime) -> SimpleNamespace:
    return SimpleNamespace(state=value, last_changed=timestamp, last_updated=timestamp)


def test_time_weighted_mean_excludes_invalid_periods_and_reports_coverage() -> None:
    mean, coverage = time_weighted_mean(
        [
            state("10", START),
            state("unavailable", START + timedelta(minutes=35)),
            state("20", START + timedelta(hours=1)),
        ],
        START,
        START + timedelta(hours=1),
    )

    assert coverage == pytest.approx(35 / 60)
    assert mean == pytest.approx(10)


def test_time_weighted_mean_accepts_exactly_sixty_percent_coverage() -> None:
    mean, coverage = time_weighted_mean(
        [state("10", START), state("unavailable", START + timedelta(minutes=36))],
        START,
        START + timedelta(hours=1),
    )

    assert coverage == pytest.approx(0.6)
    assert mean == pytest.approx(10)


def test_select_representative_snapshot_uses_latest_fetch_before_target() -> None:
    snapshots = {
        "old": {
            "weather_entity": "weather.home",
            "entries": [[(START + timedelta(hours=4)).isoformat(), 4]],
            "fetched_at": [(START - timedelta(hours=1)).isoformat()],
        },
        "new": {
            "weather_entity": "weather.home",
            "entries": [[(START + timedelta(hours=4)).isoformat(), 5]],
            "fetched_at": [(START + timedelta(hours=1)).isoformat()],
        },
    }

    selected = select_representative_snapshots(snapshots)

    candidate = selected[("weather.home", (START + timedelta(hours=4)).isoformat(), "3_6h")]
    assert candidate["snapshot_hash"] == "new"
    assert candidate["forecast_temperature"] == 5


def test_aggregate_metrics_uses_fourteen_day_target_window() -> None:
    now = START + timedelta(days=14)
    results = {
        "one": {"status": "validated", "target_at": (now - timedelta(days=1)).isoformat(), "range": "0_3h", "difference": 2},
        "two": {"status": "validated", "target_at": (now - timedelta(days=1)).isoformat(), "range": "0_3h", "difference": -1},
        "old": {"status": "validated", "target_at": (now - timedelta(days=15)).isoformat(), "range": "0_3h", "difference": 100},
    }

    metrics = aggregate_metrics(results, now)

    assert metrics["0_3h"] == {
        "windows": 2,
        "mean_difference": pytest.approx(0.5),
        "mae": pytest.approx(1.5),
        "rmse": pytest.approx(5**0.5 / 2**0.5),
    }
    assert metrics["24_48h"]["windows"] == 0


def test_validate_due_retries_recorder_unavailable() -> None:
    store = Mock()
    store.async_delay_save = Mock()
    history_source = AsyncMock(side_effect=RuntimeError("recorder unavailable"))
    with patch(
        "custom_components.heat_pump_predictor.forecast_validation.Store", return_value=store
    ):
        manager = ForecastValidationManager(Mock(), "entry", history_source=history_source)
        manager.data["snapshots"] = {
            "hash": {
                "weather_entity": "weather.home",
                "entries": [[(START - timedelta(hours=1)).isoformat(), 3]],
                "fetched_at": [(START - timedelta(hours=2)).isoformat()],
            }
        }

        import asyncio

        asyncio.run(manager.async_validate_due(START + timedelta(hours=1, minutes=10)))
        asyncio.run(manager.async_validate_due(START + timedelta(hours=2, minutes=10)))

    result = next(iter(manager.data["results"].values()))
    assert result["reason"] == "recorder_unavailable"
    assert history_source.await_count == 2


def test_validate_due_reads_configured_temperature_sensor_not_weather_entity() -> None:
    store = Mock()
    store.async_delay_save = Mock()
    history_source = AsyncMock(
        return_value={
            "sensor.outdoor_temperature": [state("10", START - timedelta(minutes=1))]
        }
    )
    with patch(
        "custom_components.heat_pump_predictor.forecast_validation.Store", return_value=store
    ):
        manager = ForecastValidationManager(
            Mock(),
            "entry",
            history_source=history_source,
            history_entity="sensor.outdoor_temperature",
        )
        target = START + timedelta(hours=1)
        manager.data["snapshots"] = {
            "hash": {
                "weather_entity": "weather.home",
                "entries": [[target.isoformat(), 12]],
                "fetched_at": [START.isoformat()],
            }
        }

        import asyncio

        asyncio.run(manager.async_validate_due(target + timedelta(hours=1, minutes=10)))

    history_source.assert_awaited_once_with(
        "sensor.outdoor_temperature", target, target + timedelta(hours=1)
    )
    assert next(iter(manager.data["results"].values()))["status"] == "validated"


def test_validate_due_caches_history_for_same_target_across_ranges() -> None:
    store = Mock()
    store.async_delay_save = Mock()
    history_source = AsyncMock(
        return_value={"sensor.temp": [state("10", START - timedelta(minutes=1))]}
    )
    with patch(
        "custom_components.heat_pump_predictor.forecast_validation.Store", return_value=store
    ):
        manager = ForecastValidationManager(
            Mock(), "entry", history_source=history_source, history_entity="sensor.temp"
        )
        target = START + timedelta(hours=24)
        manager.data["snapshots"] = {
            "short": {
                "weather_entity": "weather.home",
                "entries": [[target.isoformat(), 12]],
                "fetched_at": [(START + timedelta(hours=12)).isoformat()],
            },
            "long": {
                "weather_entity": "weather.home",
                "entries": [[target.isoformat(), 13]],
                "fetched_at": [START.isoformat()],
            },
        }

        import asyncio

        asyncio.run(manager.async_validate_due(target + timedelta(hours=1, minutes=10)))

    assert history_source.await_count == 1


def test_validate_due_prunes_expired_results_before_saving() -> None:
    store = Mock()
    store.async_delay_save = Mock()
    with patch(
        "custom_components.heat_pump_predictor.forecast_validation.Store", return_value=store
    ):
        manager = ForecastValidationManager(Mock(), "entry", history_source=AsyncMock())
        manager.data["results"] = {
            "expired": {
                "target_at": (START - timedelta(days=29)).isoformat(),
                "status": "validated",
                "difference": 1,
                "range": "0_3h",
            }
        }

        import asyncio

        asyncio.run(manager.async_validate_due(START))

    assert manager.data["results"] == {}
    store.async_delay_save.assert_called_once()


def test_validate_due_discards_malformed_restored_results() -> None:
    store = Mock()
    store.async_delay_save = Mock()
    with patch(
        "custom_components.heat_pump_predictor.forecast_validation.Store", return_value=store
    ):
        manager = ForecastValidationManager(Mock(), "entry", history_source=AsyncMock())
        manager.data["results"] = {"malformed": "not-a-result"}

        import asyncio

        asyncio.run(manager.async_validate_due(START))

    assert manager.data["results"] == {}


def test_invalid_states_are_insufficient_coverage_not_missing_history() -> None:
    store = Mock()
    store.async_delay_save = Mock()
    target = START + timedelta(hours=1)
    with patch(
        "custom_components.heat_pump_predictor.forecast_validation.Store", return_value=store
    ):
        manager = ForecastValidationManager(
            Mock(),
            "entry",
            history_source=AsyncMock(
                return_value={"sensor.temp": [state("unavailable", target)]}
            ),
            history_entity="sensor.temp",
        )
        manager.data["snapshots"] = {
            "hash": {
                "weather_entity": "weather.home",
                "entries": [[target.isoformat(), 12]],
                "fetched_at": [START.isoformat()],
            }
        }

        import asyncio

        asyncio.run(manager.async_validate_due(target + timedelta(hours=1, minutes=10)))

    result = next(iter(manager.data["results"].values()))
    assert result["reason"] == "insufficient_coverage"


def test_validate_due_replaces_result_for_newer_representative_snapshot() -> None:
    store = Mock()
    store.async_delay_save = Mock()
    history_source = AsyncMock(
            return_value={
            "weather.home": [
                state("10", START - timedelta(minutes=1)),
            ]
        }
    )
    with patch(
        "custom_components.heat_pump_predictor.forecast_validation.Store", return_value=store
    ):
        manager = ForecastValidationManager(Mock(), "entry", history_source=history_source)
        target = START + timedelta(hours=1)
        manager.data["snapshots"] = {
            "old": {
                "weather_entity": "weather.home",
                "entries": [[target.isoformat(), 10]],
                "fetched_at": [(START - timedelta(hours=1)).isoformat()],
            },
            "new": {
                "weather_entity": "weather.home",
                "entries": [[target.isoformat(), 20]],
                "fetched_at": [START.isoformat()],
            },
        }

        import asyncio

        asyncio.run(manager.async_validate_due(target + timedelta(hours=1, minutes=10)))

    result = next(iter(manager.data["results"].values()))
    assert result["snapshot_hash"] == "new"
    assert result["difference"] == pytest.approx(10)


def test_missing_recorder_entity_is_retryable() -> None:
    with patch(
        "custom_components.heat_pump_predictor.forecast_validation.Store",
        return_value=Mock(),
    ):
        manager = ForecastValidationManager(
            Mock(), "entry", history_source=AsyncMock(return_value={})
        )

    async def assert_missing_entity() -> None:
        with pytest.raises(RecorderHistoryUnavailable):
            await manager._get_history(
                "sensor.outdoor_temperature", START, START + timedelta(hours=1)
            )

    import asyncio

    asyncio.run(assert_missing_entity())


def test_recorder_adapter_uses_executor_and_complete_history_options() -> None:
    hass = Mock()
    store = Mock(hass=hass)
    recorder = Mock()
    recorder.async_add_executor_job = AsyncMock(return_value={"sensor.temp": []})
    with (
        patch("custom_components.heat_pump_predictor.forecast_validation.Store", return_value=store),
        patch("homeassistant.components.recorder.get_instance", return_value=recorder),
    ):
        manager = ForecastValidationManager(hass, "entry")
        import asyncio

        asyncio.run(manager._async_recorder_history("sensor.temp", START, START + timedelta(hours=1)))

    args = recorder.async_add_executor_job.await_args.args
    assert args[1:4] == (hass, START, START + timedelta(hours=1))
    assert args[4:] == (["sensor.temp"], None, True, False, False, True)


def test_validation_schedule_handler_delegates_current_time() -> None:
    coordinator = object.__new__(HeatPumpCoordinator)
    coordinator.forecast_validation = Mock()
    coordinator.forecast_validation.async_validate_due = AsyncMock()

    import asyncio

    asyncio.run(coordinator._handle_validation_schedule(START))

    coordinator.forecast_validation.async_validate_due.assert_awaited_once()


def test_validation_schedule_unsubscribes_on_shutdown() -> None:
    coordinator = object.__new__(HeatPumpCoordinator)
    unsubscribe = Mock()
    coordinator._unsub_validation_schedule = unsubscribe

    coordinator._async_unsubscribe_validation_schedule()

    unsubscribe.assert_called_once_with()
    assert coordinator._unsub_validation_schedule is None
