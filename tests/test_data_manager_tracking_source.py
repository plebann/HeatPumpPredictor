from datetime import datetime, timezone

from custom_components.heat_pump_predictor.data_manager import HeatPumpDataManager


def test_tracking_source_change_discards_previous_delta_baseline() -> None:
    manager = HeatPumpDataManager()
    manager.set_tracking_source("sensor.energy_a")
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    manager.process_state_update(5.0, 10.0, True, timestamp)

    assert manager.set_tracking_source("sensor.energy_b") is True
    assert manager.process_state_update(5.0, 200.0, True, timestamp) is None
