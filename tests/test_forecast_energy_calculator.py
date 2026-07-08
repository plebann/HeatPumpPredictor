"""Tests for Forecast Energy calculation."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from custom_components.heat_pump_predictor.forecast_energy import (
    ForecastEnergyCalculationError,
    ForecastEnergyCalculator,
)


class FakeHeatPumpCalculator:
    """Fake calculator for exercising the Forecast Energy seam."""

    def __init__(self) -> None:
        self.estimations: dict[float, dict[str, Any]] = {}
        self.failed_temperatures: set[float] = set()
        self.interpolated_temperatures: list[float] = []
        self.trend_adjustments: list[tuple[float, float]] = []

    def interpolate_estimation(self, temperature: float) -> dict[str, Any]:
        self.interpolated_temperatures.append(temperature)
        if temperature in self.failed_temperatures:
            raise ValueError("no data")
        return self.estimations.get(
            temperature,
            {
                "power_overall_w": 1000.0,
                "confidence": "high",
                "approximated": False,
                "approximation_source": None,
            },
        )

    def trend_adjustment(self, delta: float, temperature: float) -> float:
        self.trend_adjustments.append((delta, temperature))
        return 1.1 if delta > 0 else 0.9


def test_forecast_energy_serializes_sorted_window_with_current_temperature_seed() -> None:
    """Return the existing response shape for the first future Forecast Window."""
    calculator = FakeHeatPumpCalculator()
    calculator.estimations = {
        11.0: {
            "power_overall_w": 1000.0,
            "confidence": "high",
            "approximated": False,
            "approximation_source": None,
        },
        12.0: {
            "power_overall_w": 2000.0,
            "confidence": "approximated",
            "approximated": True,
            "approximation_source": 10,
        },
    }
    forecast = [
        {"datetime": "2026-01-01T13:00:00+00:00", "temperature": 13.0},
        {"datetime": "2026-01-01T12:00:00+00:00", "temperature": 12.0},
        {"datetime": "2026-01-01T11:00:00+00:00", "temperature": 11.0},
    ]

    result = ForecastEnergyCalculator(calculator).calculate(
        forecast,
        starting_hour=11,
        hours_ahead=2,
        current_temperature=10.0,
        now=datetime(2026, 1, 1, 10, 15, tzinfo=timezone.utc),
    )

    assert result.as_response() == {
        "total_energy_kwh": 3.3,
        "hours": [
            {
                "datetime": "2026-01-01T11:00:00+00:00",
                "temperature": 11.0,
                "temperature_delta": 1.0,
                "trend_adjustment": 1.1,
                "energy_kwh": 1.1,
                "confidence": "high",
                "approximated": False,
                "approximation_source": None,
            },
            {
                "datetime": "2026-01-01T12:00:00+00:00",
                "temperature": 12.0,
                "temperature_delta": 1.0,
                "trend_adjustment": 1.1,
                "energy_kwh": 2.2,
                "confidence": "approximated",
                "approximated": True,
                "approximation_source": 10,
            },
        ],
        "hours_requested": 2,
        "hours_returned": 2,
        "approximated_hours": 1,
        "starting_hour": 11,
    }
    assert calculator.interpolated_temperatures == [11.0, 12.0]
    assert calculator.trend_adjustments == [(1.0, 11.0), (1.0, 12.0)]


def test_forecast_energy_uses_previous_forecast_hour_for_later_window() -> None:
    """Ignore current temperature when the Forecast Window starts later."""
    calculator = FakeHeatPumpCalculator()
    forecast = [
        {"datetime": "2026-01-01T11:00:00+00:00", "temperature": 10.0},
        {"datetime": "2026-01-01T12:00:00+00:00", "temperature": 15.0},
    ]

    result = ForecastEnergyCalculator(calculator).calculate(
        forecast,
        starting_hour=12,
        hours_ahead=1,
        current_temperature=99.0,
        now=datetime(2026, 1, 1, 10, 15, tzinfo=timezone.utc),
    )

    first_hour = result.as_response()["hours"][0]
    assert first_hour["temperature_delta"] == 5.0
    assert calculator.trend_adjustments == [(5.0, 15.0)]


def test_forecast_energy_requires_previous_forecast_hour_for_later_window() -> None:
    """Raise a domain error when a later Forecast Window has no prior hour."""
    forecast = [{"datetime": "2026-01-01T12:00:00+00:00", "temperature": 15.0}]

    with pytest.raises(ForecastEnergyCalculationError) as err:
        ForecastEnergyCalculator(FakeHeatPumpCalculator()).calculate(
            forecast,
            starting_hour=12,
            hours_ahead=1,
            current_temperature=10.0,
            now=datetime(2026, 1, 1, 10, 15, tzinfo=timezone.utc),
        )

    assert err.value.reason_key == "forecast_window_too_small"
    assert err.value.placeholders == {}


@pytest.mark.parametrize(
    ("forecast", "starting_hour", "reason_key", "placeholders"),
    [
        (
            [{"datetime": "2026-01-01T11:00:00+00:00", "temperature": 11.0}],
            12,
            "forecast_window_too_small",
            {},
        ),
        (
            [{"datetime": "2026-01-01T11:00:00+00:00"}],
            11,
            "forecast_hour_missing",
            {"datetime": "2026-01-01T11:00:00+00:00"},
        ),
        (
            [{"datetime": "2026-01-01T11:00:00+00:00", "temperature": "bad"}],
            11,
            "forecast_hour_missing",
            {"datetime": "2026-01-01T11:00:00+00:00"},
        ),
    ],
)
def test_forecast_energy_raises_domain_errors(
    forecast: list[dict[str, Any]],
    starting_hour: int,
    reason_key: str,
    placeholders: dict[str, str],
) -> None:
    """Represent Forecast Energy failures without Home Assistant exceptions."""
    with pytest.raises(ForecastEnergyCalculationError) as err:
        ForecastEnergyCalculator(FakeHeatPumpCalculator()).calculate(
            forecast,
            starting_hour=starting_hour,
            hours_ahead=1,
            current_temperature=10.0,
            now=datetime(2026, 1, 1, 10, 15, tzinfo=timezone.utc),
        )

    assert err.value.reason_key == reason_key
    assert err.value.placeholders == placeholders


def test_forecast_energy_maps_approximation_failure_to_domain_error() -> None:
    """Preserve the no-data-for-approximation failure as a domain error."""
    calculator = FakeHeatPumpCalculator()
    calculator.failed_temperatures.add(11.0)

    with pytest.raises(ForecastEnergyCalculationError) as err:
        ForecastEnergyCalculator(calculator).calculate(
            [{"datetime": "2026-01-01T11:00:00+00:00", "temperature": 11.0}],
            starting_hour=11,
            hours_ahead=1,
            current_temperature=10.0,
            now=datetime(2026, 1, 1, 10, 15, tzinfo=timezone.utc),
        )

    assert err.value.reason_key == "no_data_for_approximation"
    assert err.value.placeholders == {"temperature": "11.0"}
