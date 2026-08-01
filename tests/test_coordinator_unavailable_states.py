"""Tests for coordinator handling of unavailable source sensor states."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from custom_components.heat_pump_predictor.const import (
    CONF_ENERGY_SENSOR,
    CONF_RUNNING_SENSOR,
    CONF_TEMPERATURE_SENSOR,
)
from custom_components.heat_pump_predictor.coordinator import HeatPumpCoordinator
from custom_components.heat_pump_predictor.data_manager import HeatPumpDataManager


class _StatesStub:
    """Small state registry stand-in."""

    def __init__(self, states: dict[str, str]) -> None:
        self._states = states

    def get(self, entity_id: str):
        state = self._states.get(entity_id)
        if state is None:
            return None
        return SimpleNamespace(state=state)


def _build_coordinator(states: dict[str, str]) -> HeatPumpCoordinator:
    coordinator = object.__new__(HeatPumpCoordinator)
    coordinator.hass = SimpleNamespace(states=_StatesStub(states))
    coordinator.data_manager = HeatPumpDataManager()
    coordinator._energy_entity = "sensor.energy"
    coordinator._running_entity = "binary_sensor.running"
    coordinator._temperature_entity = "sensor.outdoor_temperature"
    coordinator._forecast = None
    coordinator._bucket_observed_callbacks = []
    coordinator.config_entry = SimpleNamespace(
        data={
            CONF_ENERGY_SENSOR: coordinator._energy_entity,
            CONF_RUNNING_SENSOR: coordinator._running_entity,
            CONF_TEMPERATURE_SENSOR: coordinator._temperature_entity,
        }
    )
    coordinator._save_data = _async_noop
    return coordinator


async def _async_noop() -> None:
    """Do nothing."""


def _run_without_event_loop(coro):
    """Run a coroutine that only awaits immediately-completing test doubles."""
    try:
        coro.send(None)
    except StopIteration as err:
        return err.value
    raise AssertionError("test coroutine unexpectedly yielded")


def test_update_skips_unavailable_numeric_sensor_state() -> None:
    """Do not fail setup when HA has not produced a numeric source state yet."""
    coordinator = _build_coordinator(
        {
            "sensor.energy": "unavailable",
            "binary_sensor.running": "off",
            "sensor.outdoor_temperature": "27.5",
        }
    )

    data = _run_without_event_loop(coordinator._async_update_data())

    assert data == {"buckets": {}, "forecast": None}


def test_update_processes_numeric_sensor_states() -> None:
    """Keep processing valid numeric source states."""
    coordinator = _build_coordinator(
        {
            "sensor.energy": "3185.98",
            "binary_sensor.running": "off",
            "sensor.outdoor_temperature": "27.5",
        }
    )
    coordinator.data_manager._last_temperature = 27.5
    coordinator.data_manager._last_energy_kwh = 3185.0
    coordinator.data_manager._last_running_state = False
    coordinator.data_manager._last_update_time = datetime(
        2026, 7, 15, 16, 0, tzinfo=timezone.utc
    )

    data = _run_without_event_loop(coordinator._async_update_data())

    assert data["buckets"][27].total_energy_kwh == pytest.approx(0.98)
