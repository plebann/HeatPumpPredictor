"""Persistent forecast snapshots used by forecast validation."""
from __future__ import annotations

import hashlib
import json
import logging
import math
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from inspect import isawaitable
from typing import Any

from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)


class RecorderHistoryUnavailable(RuntimeError):
    """Recorder did not return history for the requested entity."""

STORAGE_VERSION = 1
STORAGE_KEY = "heat_pump_predictor.forecast_validation"
RETENTION = timedelta(days=28)
ENERGY_RETENTION = timedelta(days=30)
MAX_HORIZON = timedelta(hours=48)

HORIZON_RANGES = ("0_3h", "3_6h", "6_12h", "12_24h", "24_48h")
VALIDATION_DELAY = timedelta(minutes=10)
RECORDER_RETRY_WINDOW = timedelta(hours=24)
METRICS_WINDOW = timedelta(days=14)
ENERGY_HALF_LIFE_DAYS = 7.0
ENERGY_MIN_SAMPLES = 3
ENERGY_MIN_ACTUAL_KWH = 0.2
ENERGY_RECENT_LIMIT = 10
ENERGY_HORIZON_BUCKETS = ("0_3h", "4_6h", "7_12h", "13_24h", "over_24h")


def as_utc(value: datetime) -> datetime:
    """Return a datetime normalized to UTC, treating naive values as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO datetime from a weather forecast payload."""
    if not isinstance(value, str):
        return None
    try:
        return as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


def normalize_forecast_entries(
    forecast: list[dict[str, Any]], fetched_at: datetime
) -> list[list[Any]]:
    """Keep valid full-hour forecast entries within the capture horizon."""
    fetched_at = as_utc(fetched_at)
    entries: dict[str, float] = {}
    for item in forecast:
        if not isinstance(item, dict):
            continue
        target_at = parse_datetime(item.get("datetime"))
        if target_at is None or target_at.minute or target_at.second or target_at.microsecond:
            continue
        try:
            temperature = float(item.get("temperature"))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(temperature):
            continue
        horizon = target_at - fetched_at
        if horizon <= timedelta(0) or horizon >= MAX_HORIZON:
            continue
        entries[target_at.isoformat()] = temperature
    return [[target, entries[target]] for target in sorted(entries)]


def snapshot_hash(weather_entity: str, entries: list[list[Any]]) -> str:
    """Return the stable content hash for a normalized snapshot."""
    payload = {
        "entries": sorted(entries, key=lambda entry: str(entry[0])),
        "weather_entity": weather_entity,
    }
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def horizon_range(horizon: timedelta | float) -> str | None:
    """Map hours (or a timedelta) to the configured half-open range."""
    hours = horizon.total_seconds() / 3600 if isinstance(horizon, timedelta) else float(horizon)
    if hours <= 0 or hours >= 48:
        return None
    if hours < 3:
        return "0_3h"
    if hours < 6:
        return "3_6h"
    if hours < 12:
        return "6_12h"
    if hours < 24:
        return "12_24h"
    return "24_48h"


def energy_horizon_bucket(horizon: timedelta | float) -> str | None:
    """Return the energy horizon bucket after rounding up to whole hours."""
    hours = horizon.total_seconds() / 3600 if isinstance(horizon, timedelta) else float(horizon)
    rounded = math.ceil(hours)
    if rounded <= 0:
        return None
    if rounded <= 3:
        return "0_3h"
    if rounded <= 6:
        return "4_6h"
    if rounded <= 12:
        return "7_12h"
    if rounded <= 24:
        return "13_24h"
    return "over_24h"


def _numeric_state_at_or_before(
    states: list[Any], boundary: datetime
) -> tuple[float | None, str | None]:
    """Return the latest numeric state at or before a boundary and its failure reason."""
    candidates = [
        (timestamp, state)
        for timestamp, state in _timestamped_states(states)
        if timestamp <= boundary
    ]
    if not candidates:
        return None, "no_boundary_reading"
    state = candidates[-1][1]
    raw_value = _state_value(state)
    if raw_value in ("unknown", "unavailable", None):
        return None, "sensor_unavailable"
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return None, "no_boundary_reading"
    if not math.isfinite(value):
        return None, "no_boundary_reading"
    return value, None


def energy_window_actual(
    states: list[Any], start: datetime, end: datetime
) -> tuple[float | None, str | None]:
    """Calculate cumulative energy in a window and detect counter resets."""
    start = as_utc(start)
    end = as_utc(end)
    if end <= start:
        return None, "no_boundary_reading"
    ordered = _timestamped_states(states)
    start_value, reason = _numeric_state_at_or_before(states, start)
    if reason:
        return None, reason
    assert start_value is not None
    previous_numeric: float | None = start_value
    for timestamp, state in ordered:
        if timestamp <= start:
            continue
        if timestamp > end:
            break
        raw_value = _state_value(state)
        if raw_value in ("unknown", "unavailable", None):
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value):
            continue
        if previous_numeric is not None and value < previous_numeric:
            return None, "negative_difference"
        previous_numeric = value
    end_value, reason = _numeric_state_at_or_before(states, end)
    if reason:
        return None, reason
    assert start_value is not None and end_value is not None
    difference = end_value - start_value
    if difference < 0:
        return None, "negative_difference"
    return difference, None


def _state_timestamp(state: Any) -> datetime | None:
    """Return the timestamp attached to a Recorder state."""
    value = state.get("last_changed") if isinstance(state, dict) else getattr(state, "last_changed", None)
    if value is None and isinstance(state, dict):
        value = state.get("last_updated")
    if value is None:
        value = getattr(state, "last_updated", None)
    if isinstance(value, datetime):
        return as_utc(value)
    if isinstance(value, str):
        return parse_datetime(value)
    return None


def _state_value(state: Any) -> Any:
    return state.get("state") if isinstance(state, dict) else getattr(state, "state", None)


def _timestamped_states(states: list[Any]) -> list[tuple[datetime, Any]]:
    """Return Recorder states with usable timestamps in chronological order."""
    timestamped: list[tuple[datetime, Any]] = []
    for state in states:
        timestamp = _state_timestamp(state)
        if timestamp is not None:
            timestamped.append((timestamp, state))
    return sorted(timestamped, key=lambda item: item[0])


def _weighted_state_segment(
    state: Any, segment_start: datetime, segment_end: datetime
) -> tuple[float, float]:
    """Return weighted value and valid seconds for one state segment."""
    if segment_end <= segment_start:
        return 0.0, 0.0
    try:
        value = float(_state_value(state))
    except (TypeError, ValueError):
        return 0.0, 0.0
    if not math.isfinite(value):
        return 0.0, 0.0
    seconds = (segment_end - segment_start).total_seconds()
    return value * seconds, seconds


def time_weighted_mean(
    states: list[Any], start: datetime, end: datetime
) -> tuple[float | None, float]:
    """Calculate a state-time weighted mean and valid coverage for an interval."""
    start = as_utc(start)
    end = as_utc(end)
    if end <= start:
        return None, 0.0

    ordered = _timestamped_states(states)
    weighted = 0.0
    valid_seconds = 0.0
    for index, (timestamp, state) in enumerate(ordered):
        segment_start = max(timestamp, start)
        next_timestamp = ordered[index + 1][0] if index + 1 < len(ordered) else end
        segment_end = min(next_timestamp, end)
        segment_weight, segment_seconds = _weighted_state_segment(
            state, segment_start, segment_end
        )
        weighted += segment_weight
        valid_seconds += segment_seconds

    window_seconds = (end - start).total_seconds()
    coverage = valid_seconds / window_seconds
    return (weighted / valid_seconds if valid_seconds else None), coverage


def select_representative_snapshots(
    snapshots: dict[str, Any],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Select the last eligible fetch for each entity, target, and horizon range."""
    selected: dict[tuple[str, str, str], dict[str, Any]] = {}
    for content_hash, record in snapshots.items():
        for candidate in _snapshot_candidates(content_hash, record):
            key = (
                candidate["weather_entity"],
                candidate["target_at"].isoformat(),
                horizon_range(candidate["horizon_hours"]),
            )
            previous = selected.get(key)
            if previous is None or candidate["fetched_at"] > previous["fetched_at"]:
                selected[key] = candidate
    return selected


def _snapshot_candidates(content_hash: str, record: Any) -> list[dict[str, Any]]:
    """Return eligible candidates from one persisted snapshot record."""
    if not isinstance(record, dict):
        return []
    entity = record.get("weather_entity")
    entries = record.get("entries", [])
    if not isinstance(entity, str) or not isinstance(entries, list):
        return []
    candidates: list[dict[str, Any]] = []
    for fetched_value in record.get("fetched_at", []):
        fetched_at = parse_datetime(fetched_value)
        if fetched_at is None:
            continue
        candidates.extend(
            _candidates_for_fetch(content_hash, entity, entries, fetched_at)
        )
    return candidates


def _candidates_for_fetch(
    content_hash: str,
    entity: str,
    entries: list[Any],
    fetched_at: datetime,
) -> list[dict[str, Any]]:
    """Return eligible target candidates for one fetch timestamp."""
    candidates: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, list) or len(entry) != 2:
            continue
        target_at = parse_datetime(entry[0])
        if target_at is None or fetched_at >= target_at:
            continue
        horizon_hours = (target_at - fetched_at).total_seconds() / 3600
        if horizon_range(horizon_hours) is None:
            continue
        candidates.append(
            {
                "snapshot_hash": content_hash,
                "weather_entity": entity,
                "target_at": target_at,
                "fetched_at": fetched_at,
                "horizon_hours": horizon_hours,
                "forecast_temperature": float(entry[1]),
            }
        )
    return candidates


def aggregate_metrics(
    results: dict[str, Any], now: datetime, window: timedelta = METRICS_WINDOW
) -> dict[str, dict[str, float | int | None]]:
    """Aggregate validated results within the requested target-time window."""
    now = as_utc(now)
    cutoff = now - window
    grouped: dict[str, list[float]] = {range_key: [] for range_key in HORIZON_RANGES}
    for result in results.values():
        if not isinstance(result, dict) or result.get("status") != "validated":
            continue
        target_at = parse_datetime(result.get("target_at"))
        difference = result.get("difference")
        range_key = result.get("range")
        if target_at is None or target_at < cutoff or target_at > now or range_key not in grouped:
            continue
        try:
            difference = float(difference)
        except (TypeError, ValueError):
            continue
        if math.isfinite(difference):
            grouped[range_key].append(difference)
    return {
        range_key: {
            "windows": len(values),
            "mean_difference": sum(values) / len(values) if values else None,
            "mae": sum(abs(value) for value in values) / len(values) if values else None,
            "rmse": math.sqrt(sum(value * value for value in values) / len(values)) if values else None,
        }
        for range_key, values in grouped.items()
    }


def aggregate_diagnostics(
    results: dict[str, Any],
    now: datetime,
    weather_entity: str | None = None,
    window: timedelta = METRICS_WINDOW,
) -> tuple[int, dict[str, dict[str, float | int | None]], dict[str, int]]:
    """Aggregate sensor data, counting each validated target window once."""
    now = as_utc(now)
    cutoff = now - window
    metrics: dict[str, list[float]] = {range_key: [] for range_key in HORIZON_RANGES}
    unvalidated: dict[str, int] = {}
    validated_windows: set[tuple[str, str]] = set()

    for result_key, result in results.items():
        context = _diagnostic_result_context(result_key, result, cutoff, now, weather_entity)
        if context is None:
            continue
        entity, target_key = context
        _add_diagnostic_result(
            result, entity, target_key, metrics, validated_windows, unvalidated
        )

    return (
        len(validated_windows),
        _build_metrics(metrics),
        unvalidated,
    )


def _diagnostic_result_context(
    result_key: str,
    result: Any,
    cutoff: datetime,
    now: datetime,
    weather_entity: str | None,
) -> tuple[str, str] | None:
    """Return the entity and target key when a result belongs in the window."""
    if not isinstance(result, dict):
        return None
    target_at = parse_datetime(result.get("target_at"))
    if target_at is None or target_at < cutoff or target_at > now:
        return None
    entity = result.get("weather_entity")
    entity = entity if isinstance(entity, str) else result_key.split("|", 1)[0]
    if weather_entity is not None and entity != weather_entity:
        return None
    return entity, target_at.isoformat()


def _add_diagnostic_result(
    result: dict[str, Any],
    entity: str,
    target_key: str,
    metrics: dict[str, list[float]],
    validated_windows: set[tuple[str, str]],
    unvalidated: dict[str, int],
) -> None:
    """Add one result to validated metrics or unvalidated counters."""
    if result.get("status") != "validated":
        reason = result.get("reason") or "unknown"
        unvalidated[reason] = unvalidated.get(reason, 0) + 1
        return
    validated_windows.add((entity, target_key))
    range_key = result.get("range")
    try:
        difference = float(result.get("difference"))
    except (TypeError, ValueError):
        return
    if range_key in metrics and math.isfinite(difference):
        metrics[range_key].append(difference)


def _build_metrics(
    grouped: dict[str, list[float]],
) -> dict[str, dict[str, float | int | None]]:
    """Build the public metric shape from differences grouped by range."""
    return {
        range_key: {
            "windows": len(values),
            "mean_difference": sum(values) / len(values) if values else None,
            "mae": sum(abs(value) for value in values) / len(values) if values else None,
            "rmse": math.sqrt(sum(value * value for value in values) / len(values))
            if values
            else None,
        }
        for range_key, values in grouped.items()
    }


class ForecastValidationManager:
    """Own the separately-retained forecast snapshot store."""

    def __init__(
        self,
        hass: Any,
        entry_id: str,
        history_source: Callable[[str, datetime, datetime], Any] | None = None,
        history_entity: str | None = None,
        energy_entity: str | None = None,
        energy_half_life_days: float = ENERGY_HALF_LIFE_DAYS,
    ) -> None:
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry_id}")
        self._data: dict[str, Any] = {"snapshots": {}, "results": {}}
        self._history_source = history_source or self._async_recorder_history
        self._history_entity = history_entity
        self._energy_entity = energy_entity
        self._energy_half_life_days = max(float(energy_half_life_days), 0.1)
        self._callbacks: list[Callable[[], None]] = []

    @property
    def data(self) -> dict[str, Any]:
        """Expose the in-memory data for diagnostics and tests."""
        return self._data

    async def async_load(self) -> None:
        """Load snapshots, ignoring an incompatible or damaged store."""
        try:
            loaded = await self._store.async_load()
            if isinstance(loaded, dict) and isinstance(loaded.get("snapshots"), dict):
                snapshots = {
                    content_hash: record
                    for content_hash, record in loaded["snapshots"].items()
                    if isinstance(content_hash, str) and self._valid_snapshot(record)
                }
                self._data = {
                    "snapshots": snapshots,
                    "results": loaded.get("results", {})
                    if isinstance(loaded.get("results", {}), dict)
                    else {},
                    "energy_observations": loaded.get("energy_observations", {})
                    if isinstance(loaded.get("energy_observations", {}), dict)
                    else {},
                    "energy_results": loaded.get("energy_results", {})
                    if isinstance(loaded.get("energy_results", {}), dict)
                    else {},
                }
            elif loaded is not None:
                _LOGGER.warning("Ignoring invalid forecast validation storage")
        except Exception:
            _LOGGER.warning("Unable to load forecast validation storage", exc_info=True)

    async def async_capture(
        self,
        weather_entity: str,
        forecast: list[dict[str, Any]],
        fetched_at: datetime,
    ) -> None:
        """Capture a normalized forecast without changing prior snapshots."""
        fetched_at = as_utc(fetched_at)
        entries = normalize_forecast_entries(forecast, fetched_at)
        if entries:
            content_hash = snapshot_hash(weather_entity, entries)
            snapshots = self._data.setdefault("snapshots", {})
            record = snapshots.setdefault(
                content_hash,
                {
                    "weather_entity": weather_entity,
                    "entries": entries,
                    "fetched_at": [],
                },
            )
            fetched_iso = fetched_at.isoformat()
            if fetched_iso not in record.setdefault("fetched_at", []):
                record["fetched_at"].append(fetched_iso)
        self._prune(fetched_at)
        self._store.async_delay_save(lambda: self._data, 5)

    async def async_save(self) -> None:
        """Flush the current snapshot data to Home Assistant storage."""
        self._prune(datetime.now(timezone.utc))
        await self._store.async_save(self._data)

    async def async_prune(self, now: datetime) -> None:
        """Remove records outside the retention window and save the result."""
        now = as_utc(now)
        self._prune(now)
        await self._store.async_save(self._data)

    def async_register_update_callback(self, callback_fn: Callable[[], None]) -> Callable[[], None]:
        """Register a callback invoked after validation changes the store."""
        self._callbacks.append(callback_fn)

        def unsubscribe() -> None:
            if callback_fn in self._callbacks:
                self._callbacks.remove(callback_fn)

        return unsubscribe

    async def async_validate_due(self, now: datetime) -> None:
        """Validate completed forecast windows against Recorder history."""
        now = as_utc(now)
        self._prune(now)
        selected = select_representative_snapshots(self._data.get("snapshots", {}))
        results = self._data.setdefault("results", {})
        history_cache: dict[tuple[str, datetime], list[Any] | Exception] = {}
        for key, candidate in selected.items():
            result_key = "|".join((key[0], key[1], key[2]))
            existing = results.get(result_key)
            if not isinstance(existing, dict):
                existing = None
            target_at = candidate["target_at"]
            if not self._should_validate(existing, candidate, target_at, now):
                continue
            history_entity = self._history_entity or candidate["weather_entity"]
            result = await self._validate_candidate(
                candidate, result_key, history_cache, history_entity, now
            )
            results[result_key] = result
        await self._async_validate_energy_due(now)
        self._store.async_delay_save(lambda: self._data, 5)
        # Notify every scheduled tick so rolling 14-day aggregates expire old
        # samples even when no new validation result was written.
        for callback_fn in tuple(self._callbacks):
            callback_fn()

    async def async_record_energy_forecast(
        self, called_at: datetime, result: Any
    ) -> None:
        """Persist a successful public energy forecast for later validation."""
        if not self._energy_entity:
            return
        hours = getattr(result, "hours", None)
        predicted = getattr(result, "total_energy_kwh", None)
        if not isinstance(hours, list) or not hours or predicted is None:
            return
        try:
            predicted = float(predicted)
        except (TypeError, ValueError):
            return
        if not math.isfinite(predicted) or predicted < 0:
            return
        timestamps = [as_utc(hour.datetime) for hour in hours]
        window_start = timestamps[0]
        window_end = timestamps[-1] + timedelta(hours=1)
        called_at = as_utc(called_at)
        horizon = window_end - called_at
        bucket = energy_horizon_bucket(horizon)
        if bucket is None:
            return
        key = "|".join((self._energy_entity, window_start.isoformat(), window_end.isoformat()))
        observations = self._data.setdefault("energy_observations", {})
        candidate = {
            "energy_entity": self._energy_entity,
            "called_at": called_at.isoformat(),
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "selected_hours": [value.isoformat() for value in timestamps],
            "hours_requested": len(timestamps),
            "hours_returned": len(timestamps),
            "predicted_kwh": predicted,
            "horizon_hours": math.ceil(horizon.total_seconds() / 3600),
            "horizon_bucket": bucket,
            "status": "pending",
        }
        existing = observations.get(key)
        existing_called_at = parse_datetime(existing.get("called_at")) if isinstance(existing, dict) else None
        if not isinstance(existing, dict) or existing_called_at is None or existing_called_at > called_at:
            observations[key] = candidate
            self._data.setdefault("energy_results", {}).pop(key, None)
        self._store.async_delay_save(lambda: self._data, 5)

    async def _async_validate_energy_due(self, now: datetime) -> None:
        """Validate matured energy observations against cumulative Recorder history."""
        if not self._energy_entity:
            return
        observations = self._data.setdefault("energy_observations", {})
        results = self._data.setdefault("energy_results", {})
        cache: dict[tuple[str, datetime, datetime], list[Any] | Exception] = {}
        for key, observation in observations.items():
            if not isinstance(observation, dict):
                continue
            start = parse_datetime(observation.get("window_start"))
            end = parse_datetime(observation.get("window_end"))
            if start is None or end is None or end + VALIDATION_DELAY > now:
                continue
            existing = results.get(key)
            if isinstance(existing, dict) and existing.get("reason") != "recorder_unavailable":
                continue
            entity = observation.get("energy_entity")
            if not isinstance(entity, str):
                continue
            cache_key = (entity, start, end)
            if cache_key not in cache:
                try:
                    cache[cache_key] = await self._get_history(entity, start, end)
                except Exception as err:
                    cache[cache_key] = err
            history = cache[cache_key]
            if isinstance(history, Exception):
                results[key] = self._energy_result(observation, "recorder_unavailable", now)
                continue
            actual, reason = energy_window_actual(history, start, end)
            if reason:
                results[key] = self._energy_result(observation, reason, now)
                continue
            assert actual is not None
            results[key] = self._energy_result(observation, None, now, actual)

    @staticmethod
    def _energy_result(
        observation: dict[str, Any], reason: str | None, now: datetime, actual: float | None = None
    ) -> dict[str, Any]:
        """Build a persisted energy validation result."""
        accuracy = None
        if actual is not None and actual >= ENERGY_MIN_ACTUAL_KWH and actual > 0:
            accuracy = float(observation["predicted_kwh"]) / actual * 100
        return {
            **observation,
            "status": "validated" if reason is None else "skipped",
            "actual_kwh": actual,
            "accuracy_percent": accuracy,
            "reason": reason or ("actual_too_small" if actual is not None and actual < ENERGY_MIN_ACTUAL_KWH else None),
            "validated_at": now.isoformat(),
        }

    def energy_accuracy(self, now: datetime) -> dict[str, Any]:
        """Return source-specific EWMA and recent accuracy diagnostics."""
        now = as_utc(now)
        validated = [
            result for result in self._data.get("energy_results", {}).values()
            if isinstance(result, dict)
            and result.get("status") == "validated"
            and result.get("energy_entity") == self._energy_entity
            and isinstance(result.get("actual_kwh"), (int, float))
        ]
        validated.sort(key=lambda result: result.get("window_end", ""))
        overall_p = overall_a = 0.0
        bucket_state = {
            bucket: {"predicted_kwh": 0.0, "actual_kwh": 0.0, "samples": 0, "effective_samples": 0.0}
            for bucket in ENERGY_HORIZON_BUCKETS
        }
        previous_end: datetime | None = None
        recent: list[float] = []
        for result in validated:
            end = parse_datetime(result.get("window_end"))
            actual = float(result["actual_kwh"])
            predicted = float(result.get("predicted_kwh", 0))
            if end is None or actual < 0 or not math.isfinite(predicted):
                continue
            if previous_end is None:
                decay = 1.0
            else:
                decay = math.exp(-math.log(2) * max((end - previous_end).total_seconds(), 0) / (self._energy_half_life_days * 86400))
            overall_p = overall_p * decay + predicted
            overall_a = overall_a * decay + actual
            bucket = result.get("horizon_bucket")
            if bucket in bucket_state:
                state = bucket_state[bucket]
                state["predicted_kwh"] = state["predicted_kwh"] * decay + predicted
                state["actual_kwh"] = state["actual_kwh"] * decay + actual
                state["samples"] += 1
                state["effective_samples"] = state["effective_samples"] * decay + 1
            if result.get("accuracy_percent") is not None:
                recent.append(float(result["accuracy_percent"]))
            previous_end = end
        recent = recent[-ENERGY_RECENT_LIMIT:]
        return {
            "accuracy": overall_p / overall_a * 100 if len(validated) >= ENERGY_MIN_SAMPLES and overall_a > 0 else None,
            "samples": len(validated),
            "effective_samples": sum(state["effective_samples"] for state in bucket_state.values()),
            "recent_accuracy": sum(recent) / len(recent) if recent else None,
            "half_life_days": self._energy_half_life_days,
            "buckets": {
                bucket: {
                    **state,
                    "accuracy": state["predicted_kwh"] / state["actual_kwh"] * 100
                    if state["samples"] >= ENERGY_MIN_SAMPLES and state["actual_kwh"] > 0
                    else None,
                }
                for bucket, state in bucket_state.items()
            },
            "latest": validated[-1] if validated else None,
        }

    async def _validate_candidate(
        self,
        candidate: dict[str, Any],
        result_key: str,
        history_cache: dict[tuple[str, datetime], list[Any] | Exception],
        history_entity: str,
        now: datetime,
    ) -> dict[str, Any]:
        """Validate one candidate and convert Recorder failures to a result."""
        target_at = candidate["target_at"]
        try:
            states = await self._history_for_target(history_cache, history_entity, target_at)
        except Exception:
            _LOGGER.warning("Recorder history unavailable for %s", result_key, exc_info=True)
            return self._result(candidate, "unvalidated", "recorder_unavailable", now)
        return self._result_from_states(candidate, states, now)

    @staticmethod
    def _should_validate(
        existing: dict[str, Any] | None,
        candidate: dict[str, Any],
        target_at: datetime,
        now: datetime,
    ) -> bool:
        """Return whether a candidate is due or needs a Recorder retry."""
        if target_at + timedelta(hours=1) + VALIDATION_DELAY > now:
            return False
        same_snapshot = existing is not None and (
            existing.get("snapshot_hash") == candidate["snapshot_hash"]
            and existing.get("fetched_at") == candidate["fetched_at"].isoformat()
        )
        if same_snapshot and (
            existing.get("status") == "validated"
            or existing.get("reason") != "recorder_unavailable"
        ):
            return False
        return not (
            existing is not None
            and now > target_at + timedelta(hours=1) + RECORDER_RETRY_WINDOW
        )

    async def _history_for_target(
        self,
        cache: dict[tuple[str, datetime], list[Any] | Exception],
        entity: str,
        target_at: datetime,
    ) -> list[Any]:
        """Read or reuse Recorder history for one actual-temperature window."""
        cache_key = (entity, target_at)
        if cache_key not in cache:
            try:
                cache[cache_key] = await self._get_history(
                    entity, target_at, target_at + timedelta(hours=1)
                )
            except Exception as err:
                cache[cache_key] = err
        cached_history = cache[cache_key]
        if isinstance(cached_history, Exception):
            raise cached_history
        return cached_history

    @staticmethod
    def _result_from_states(
        candidate: dict[str, Any], states: list[Any], now: datetime
    ) -> dict[str, Any]:
        """Build a validation result from Recorder states."""
        target_at = candidate["target_at"]
        actual_mean, coverage = time_weighted_mean(
            states, target_at, target_at + timedelta(hours=1)
        )
        if actual_mean is None:
            reason = "insufficient_coverage" if states else "no_recorded_states"
            result = ForecastValidationManager._result(candidate, "unvalidated", reason, now)
            result["coverage"] = coverage
            return result
        if coverage < 0.60:
            result = ForecastValidationManager._result(
                candidate, "unvalidated", "insufficient_coverage", now
            )
            result["actual_mean"] = actual_mean
            result["coverage"] = coverage
            return result
        result = ForecastValidationManager._result(candidate, "validated", None, now)
        result["actual_mean"] = actual_mean
        result["coverage"] = coverage
        result["difference"] = candidate["forecast_temperature"] - actual_mean
        return result

    async def _get_history(self, entity: str, start: datetime, end: datetime) -> list[Any]:
        value = self._history_source(entity, start, end)
        if isawaitable(value):
            value = await value
        if isinstance(value, dict):
            if entity not in value:
                raise RecorderHistoryUnavailable(entity)
            value = value[entity]
        return value if isinstance(value, list) else []

    async def _async_recorder_history(self, entity: str, start: datetime, end: datetime) -> dict[str, list[Any]]:
        """Read Recorder history without blocking the Home Assistant loop."""
        from homeassistant.components.recorder import get_instance, history

        recorder = get_instance(self._store.hass)
        return await recorder.async_add_executor_job(
            history.get_significant_states,
            self._store.hass,
            start,
            end,
            [entity],
            None,
            True,
            False,
            False,
            True,
        )

    @staticmethod
    def _result(candidate: dict[str, Any], status: str, reason: str | None, now: datetime) -> dict[str, Any]:
        return {
            "snapshot_hash": candidate["snapshot_hash"],
            "fetched_at": candidate["fetched_at"].isoformat(),
            "target_at": candidate["target_at"].isoformat(),
            "weather_entity": candidate["weather_entity"],
            "range": horizon_range(candidate["horizon_hours"]),
            "horizon_hours": candidate["horizon_hours"],
            "forecast_temperature": candidate["forecast_temperature"],
            "status": status,
            "reason": reason,
            "actual_mean": None,
            "coverage": None,
            "difference": None,
            "validated_at": now.isoformat(),
        }

    @staticmethod
    def _valid_snapshot(record: Any) -> bool:
        """Check the nested shape needed by capture and pruning."""
        if not isinstance(record, dict) or not isinstance(record.get("weather_entity"), str):
            return False
        entries = record.get("entries")
        fetched_at = record.get("fetched_at")
        if not isinstance(entries, list) or not isinstance(fetched_at, list) or not fetched_at:
            return False
        if any(parse_datetime(value) is None for value in fetched_at):
            return False
        for entry in entries:
            if not isinstance(entry, list) or len(entry) != 2:
                return False
            target_at = parse_datetime(entry[0])
            try:
                temperature = float(entry[1])
            except (TypeError, ValueError):
                return False
            if (
                target_at is None
                or target_at.minute
                or target_at.second
                or target_at.microsecond
                or not math.isfinite(temperature)
            ):
                return False
        return True

    def _prune(self, now: datetime) -> None:
        cutoff = now - RETENTION
        self._prune_snapshots(cutoff)
        self._prune_results(cutoff)
        energy_cutoff = now - ENERGY_RETENTION
        for collection_name in ("energy_observations", "energy_results"):
            collection = self._data.setdefault(collection_name, {})
            for key, record in list(collection.items()):
                if not isinstance(record, dict):
                    del collection[key]
                    continue
                timestamp = parse_datetime(
                    record.get("validated_at") or record.get("called_at")
                )
                if timestamp is not None and timestamp < energy_cutoff:
                    del collection[key]

    def _prune_snapshots(self, cutoff: datetime) -> None:
        """Remove malformed and expired snapshot records."""
        snapshots = self._data.setdefault("snapshots", {})
        for content_hash, record in list(snapshots.items()):
            if not self._valid_snapshot(record):
                del snapshots[content_hash]
                continue
            timestamps = []
            for timestamp in record.get("fetched_at", []):
                parsed = parse_datetime(timestamp)
                if parsed is not None and parsed >= cutoff:
                    timestamps.append(timestamp)
            if timestamps:
                record["fetched_at"] = timestamps
            else:
                del snapshots[content_hash]

    def _prune_results(self, cutoff: datetime) -> None:
        """Remove malformed and expired validation results."""
        results = self._data.setdefault("results", {})
        for key, result in list(results.items()):
            if not isinstance(result, dict):
                del results[key]
                continue
            target_value = result.get("target_at")
            target_at = parse_datetime(target_value)
            if target_at is not None and target_at < cutoff:
                del results[key]
