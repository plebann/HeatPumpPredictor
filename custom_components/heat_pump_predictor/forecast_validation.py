"""Persistent forecast snapshots used by forecast validation."""
from __future__ import annotations

import hashlib
import json
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = "heat_pump_predictor.forecast_validation"
RETENTION = timedelta(days=28)
MAX_HORIZON = timedelta(hours=48)

HORIZON_RANGES = ("0_3h", "3_6h", "6_12h", "12_24h", "24_48h")


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


class ForecastValidationManager:
    """Own the separately-retained forecast snapshot store."""

    def __init__(self, hass: Any, entry_id: str) -> None:
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry_id}")
        self._data: dict[str, Any] = {"snapshots": {}, "results": {}}

    @property
    def data(self) -> dict[str, Any]:
        """Expose the in-memory data for diagnostics and tests."""
        return self._data

    async def async_load(self) -> None:
        """Load snapshots, ignoring an incompatible or damaged store."""
        try:
            loaded = await self._store.async_load()
            if isinstance(loaded, dict) and isinstance(loaded.get("snapshots"), dict):
                self._data = {
                    "snapshots": loaded["snapshots"],
                    "results": loaded.get("results", {})
                    if isinstance(loaded.get("results", {}), dict)
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
        await self._store.async_save(self._data)

    async def async_prune(self, now: datetime) -> None:
        """Remove records outside the retention window and save the result."""
        self._prune(as_utc(now))
        await self.async_save()

    def _prune(self, now: datetime) -> None:
        cutoff = now - RETENTION
        snapshots = self._data.setdefault("snapshots", {})
        for content_hash, record in list(snapshots.items()):
            timestamps = [
                timestamp
                for timestamp in record.get("fetched_at", [])
                if (parsed := parse_datetime(timestamp)) is not None and parsed >= cutoff
            ]
            if timestamps:
                record["fetched_at"] = timestamps
            else:
                del snapshots[content_hash]
        results = self._data.setdefault("results", {})
        for key, result in list(results.items()):
            target_at = parse_datetime(result.get("target_at")) if isinstance(result, dict) else None
            if target_at is not None and target_at < cutoff:
                del results[key]
