from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from custom_components.heat_pump_predictor.sensors.forecast_validation import (
    ForecastTemperatureValidationSensor,
)


def test_diagnostic_sensor_reports_zero_ranges_without_data() -> None:
    manager = Mock()
    manager.data = {"results": {}}
    manager.async_register_update_callback.return_value = lambda: None
    coordinator = Mock()
    coordinator.config_entry = SimpleNamespace(entry_id="entry-1")
    coordinator.device_info = {"identifiers": {("heat_pump_predictor", "entry-1")}}
    coordinator.last_update_success = True
    coordinator.forecast_validation = manager
    coordinator.async_add_listener.return_value = lambda: None

    sensor = ForecastTemperatureValidationSensor(
        Mock(), coordinator, "weather.home"
    )
    sensor._refresh_attributes(datetime(2026, 1, 1, tzinfo=timezone.utc))

    assert sensor.native_value == 0
    assert sensor.extra_state_attributes["weather_entity"] == "weather.home"
    assert sensor.extra_state_attributes["description"].startswith(
        "różnica prognozy punktowej względem średniej godzinnej"
    )
    assert all(
        values == {"windows": 0, "mean_difference": None, "mae": None, "rmse": None}
        for values in sensor.extra_state_attributes["ranges"].values()
    )
