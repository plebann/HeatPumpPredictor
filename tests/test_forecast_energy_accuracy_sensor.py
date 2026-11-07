from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
import asyncio

from custom_components.heat_pump_predictor.sensors.forecast_energy_accuracy import (
    ForecastEnergyAccuracySensor,
)


def test_energy_accuracy_sensor_publishes_unknown_and_diagnostics() -> None:
    manager = Mock()
    manager.async_register_update_callback.return_value = lambda: None
    manager.energy_accuracy.return_value = {
        "accuracy": None,
        "half_life_days": 7.0,
        "samples": 0,
        "effective_samples": 0.0,
        "recent_accuracy": None,
        "buckets": {},
        "latest": None,
    }
    coordinator = Mock()
    coordinator.config_entry = SimpleNamespace(entry_id="entry-1")
    coordinator.device_info = {"identifiers": {("heat_pump_predictor", "entry-1")}}
    coordinator.last_update_success = True
    coordinator.forecast_validation = manager
    coordinator.energy_entity = "sensor.heat_pump_energy"
    coordinator.async_add_listener.return_value = lambda: None

    sensor = ForecastEnergyAccuracySensor(Mock(), coordinator)
    sensor._refresh(datetime(2026, 1, 1, tzinfo=timezone.utc))

    assert sensor.native_value is None
    assert sensor.extra_state_attributes["energy_entity"] == "sensor.heat_pump_energy"
    assert "end-to-end accuracy" in sensor.extra_state_attributes["description"]


def test_energy_accuracy_sensor_subscribes_and_cleans_up() -> None:
    manager = Mock()
    unsubscribe = Mock()
    manager.async_register_update_callback.return_value = unsubscribe
    manager.energy_accuracy.return_value = {
        "accuracy": 100.0,
        "half_life_days": 7.0,
        "samples": 3,
        "effective_samples": 2.5,
        "recent_accuracy": 100.0,
        "buckets": {},
        "latest": {"status": "validated"},
    }
    coordinator = Mock()
    coordinator.config_entry = SimpleNamespace(entry_id="entry-1")
    coordinator.device_info = {"identifiers": {("heat_pump_predictor", "entry-1")}}
    coordinator.last_update_success = True
    coordinator.forecast_validation = manager
    coordinator.energy_entity = "sensor.heat_pump_energy"
    coordinator.async_add_listener.return_value = lambda: None

    sensor = ForecastEnergyAccuracySensor(Mock(), coordinator)
    asyncio.run(sensor.async_added_to_hass())
    asyncio.run(sensor.async_will_remove_from_hass())

    manager.async_register_update_callback.assert_called_once()
    unsubscribe.assert_called_once()
