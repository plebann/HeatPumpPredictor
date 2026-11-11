"""Tests for Forecast Energy calculation."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

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


@pytest.mark.parametrize(
    "now",
    [
        datetime(2026, 1, 1, 6, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 6, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 6, 59, 59, tzinfo=timezone.utc),
    ],
)
def test_forecast_energy_selects_current_hour_until_it_ends(now: datetime) -> None:
    """Treat starting_hour as the complete current hourly bucket."""
    calculator = FakeHeatPumpCalculator()
    forecast = [
        {"datetime": "2026-01-02T06:00:00+00:00", "temperature": 20.0},
        {"datetime": "2026-01-01T07:00:00+00:00", "temperature": 12.0},
        {"datetime": "2026-01-01T06:00:00+00:00", "temperature": 11.0},
    ]

    result = ForecastEnergyCalculator(calculator).calculate(
        forecast,
        starting_hour=6,
        hours_ahead=2,
        current_temperature=10.0,
        now=now,
    )

    response = result.as_response()
    assert [hour["datetime"] for hour in response["hours"]] == [
        "2026-01-01T06:00:00+00:00",
        "2026-01-01T07:00:00+00:00",
    ]
    assert response["hours"][0]["temperature_delta"] == 1.0
    assert calculator.trend_adjustments[0] == (1.0, 11.0)


def test_forecast_energy_selects_next_starting_hour_after_current_hour_ends() -> None:
    """Stop selecting the current bucket at its exclusive end boundary."""
    calculator = FakeHeatPumpCalculator()
    forecast = [
        {"datetime": "2026-01-01T06:00:00+00:00", "temperature": 11.0},
        {"datetime": "2026-01-02T05:00:00+00:00", "temperature": 19.0},
        {"datetime": "2026-01-02T06:00:00+00:00", "temperature": 20.0},
    ]

    result = ForecastEnergyCalculator(calculator).calculate(
        forecast,
        starting_hour=6,
        hours_ahead=1,
        current_temperature=10.0,
        now=datetime(2026, 1, 1, 7, 0, tzinfo=timezone.utc),
    )

    first_hour = result.as_response()["hours"][0]
    assert first_hour["datetime"] == "2026-01-02T06:00:00+00:00"
    assert first_hour["temperature_delta"] == 1.0


def test_forecast_energy_omits_current_hour_trend_without_current_temperature() -> None:
    """Calculate the current bucket without a trend seed when the sensor is unavailable."""
    calculator = FakeHeatPumpCalculator()

    result = ForecastEnergyCalculator(calculator).calculate(
        [{"datetime": "2026-01-01T06:00:00+00:00", "temperature": 11.0}],
        starting_hour=6,
        hours_ahead=1,
        current_temperature=None,
        now=datetime(2026, 1, 1, 6, 30, tzinfo=timezone.utc),
    )

    first_hour = result.as_response()["hours"][0]
    assert first_hour["temperature_delta"] is None
    assert first_hour["trend_adjustment"] is None
    assert calculator.trend_adjustments == []


def test_forecast_energy_matches_current_hour_after_timezone_conversion() -> None:
    """Match forecast instants after converting them into the caller's local timezone."""
    warsaw = ZoneInfo("Europe/Warsaw")

    result = ForecastEnergyCalculator(FakeHeatPumpCalculator()).calculate(
        [{"datetime": "2026-01-01T05:00:00+00:00", "temperature": 11.0}],
        starting_hour=6,
        hours_ahead=1,
        current_temperature=10.0,
        now=datetime(2026, 1, 1, 6, 30, tzinfo=warsaw),
    )

    assert result.as_response()["hours"][0]["datetime"] == "2026-01-01T06:00:00+01:00"


def test_forecast_energy_seeds_current_bucket_at_fractional_utc_offset() -> None:
    """Recognize a UTC-aligned forecast within a fractional-offset local bucket."""
    kolkata = ZoneInfo("Asia/Kolkata")
    calculator = FakeHeatPumpCalculator()

    result = ForecastEnergyCalculator(calculator).calculate(
        [{"datetime": "2026-01-01T01:00:00+00:00", "temperature": 11.0}],
        starting_hour=6,
        hours_ahead=1,
        current_temperature=10.0,
        now=datetime(2026, 1, 1, 6, 45, tzinfo=kolkata),
    )

    first_hour = result.as_response()["hours"][0]
    assert first_hour["datetime"] == "2026-01-01T06:30:00+05:30"
    assert first_hour["temperature_delta"] == 1.0
    assert calculator.trend_adjustments == [(1.0, 11.0)]


@pytest.mark.parametrize(
    ("now_utc", "expected_offset"),
    [
        (datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc), "+02:00"),
        (datetime(2026, 10, 25, 1, 30, tzinfo=timezone.utc), "+01:00"),
    ],
)
def test_forecast_energy_selects_active_repeated_dst_hour(
    now_utc: datetime, expected_offset: str
) -> None:
    """Distinguish both occurrences of a repeated local hour by their instant."""
    warsaw = ZoneInfo("Europe/Warsaw")
    forecast = [
        {"datetime": "2026-10-25T01:00:00+00:00", "temperature": 12.0},
        {"datetime": "2026-10-25T00:00:00+00:00", "temperature": 11.0},
    ]

    result = ForecastEnergyCalculator(FakeHeatPumpCalculator()).calculate(
        forecast,
        starting_hour=2,
        hours_ahead=1,
        current_temperature=10.0,
        now=now_utc.astimezone(warsaw),
    )

    selected = result.as_response()["hours"][0]["datetime"]
    assert selected.endswith(expected_offset)


def test_forecast_energy_skips_nonexistent_spring_forward_hour() -> None:
    """Select the next real occurrence when today's requested wall hour does not exist."""
    warsaw = ZoneInfo("Europe/Warsaw")
    forecast = [
        {"datetime": "2026-03-29T01:00:00+00:00", "temperature": 10.0},
        {"datetime": "2026-03-29T23:00:00+00:00", "temperature": 11.0},
        {"datetime": "2026-03-30T00:00:00+00:00", "temperature": 12.0},
    ]

    result = ForecastEnergyCalculator(FakeHeatPumpCalculator()).calculate(
        forecast,
        starting_hour=2,
        hours_ahead=1,
        current_temperature=9.0,
        now=datetime(2026, 3, 29, 0, 30, tzinfo=timezone.utc).astimezone(warsaw),
    )

    assert result.as_response()["hours"][0]["datetime"] == "2026-03-30T02:00:00+02:00"


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
