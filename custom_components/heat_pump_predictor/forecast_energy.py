"""Forecast Energy calculation module."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol


class HeatPumpForecastCalculator(Protocol):
    """Calculator interface used by Forecast Energy calculation."""

    def interpolate_estimation(self, temperature: float) -> dict[str, Any]:
        """Estimate power metrics for a forecast outdoor temperature."""

    def trend_adjustment(self, delta: float, temperature: float) -> float:
        """Return the trend multiplier for a forecast outdoor temperature."""


class ForecastEnergyCalculationError(Exception):
    """Domain error raised when Forecast Energy cannot be calculated."""

    def __init__(self, reason_key: str, placeholders: dict[str, str] | None = None) -> None:
        """Initialize the domain error."""
        super().__init__(reason_key)
        self.reason_key = reason_key
        self.placeholders = {} if placeholders is None else placeholders


@dataclass(frozen=True)
class ForecastHourEnergy:
    """Forecast Energy details for one forecast hour."""

    datetime: datetime
    temperature: float
    temperature_delta: float | None
    trend_adjustment: float | None
    energy_kwh: float
    confidence: str
    approximated: bool
    approximation_source: Any

    def as_response(self) -> dict[str, Any]:
        """Serialize the hour using the existing Home Assistant response shape."""
        return {
            "datetime": self.datetime.isoformat(),
            "temperature": self.temperature,
            "temperature_delta": self.temperature_delta,
            "trend_adjustment": self.trend_adjustment,
            "energy_kwh": round(self.energy_kwh, 3),
            "confidence": self.confidence,
            "approximated": self.approximated,
            "approximation_source": self.approximation_source,
        }


@dataclass(frozen=True)
class ForecastEnergyResult:
    """Forecast Energy result for a forecast window."""

    total_energy_kwh: float
    hours: list[ForecastHourEnergy]
    hours_requested: int
    starting_hour: int

    def as_response(self) -> dict[str, Any]:
        """Serialize the result using the existing Home Assistant response shape."""
        return {
            "total_energy_kwh": round(self.total_energy_kwh, 3),
            "hours": [hour.as_response() for hour in self.hours],
            "hours_requested": self.hours_requested,
            "hours_returned": len(self.hours),
            "approximated_hours": sum(1 for hour in self.hours if hour.approximated),
            "starting_hour": self.starting_hour,
        }


class ForecastEnergyCalculator:
    """Calculate Forecast Energy from cached hourly forecast data."""

    def __init__(self, calculator: HeatPumpForecastCalculator) -> None:
        """Initialize with the heat pump calculator dependency."""
        self._calculator = calculator

    def calculate(
        self,
        forecast: list[dict[str, Any]],
        *,
        starting_hour: int,
        hours_ahead: int,
        current_temperature: float | None,
        now: datetime,
    ) -> ForecastEnergyResult:
        """Calculate Forecast Energy for a requested forecast window."""
        now_local = self._as_local(now, now)
        parsed_forecast = self._parse_forecast(forecast, now_local)
        start_index = self._find_start_index(parsed_forecast, now_local, starting_hour)
        window = parsed_forecast[start_index : start_index + hours_ahead]

        if len(window) < hours_ahead:
            raise ForecastEnergyCalculationError("forecast_window_too_small")

        previous_temp = self._previous_temperature(
            parsed_forecast,
            start_index,
            now_local,
            current_temperature,
        )

        total_energy_kwh = 0.0
        hours: list[ForecastHourEnergy] = []

        for dt_val, payload in window:
            temp_float = self._temperature_from_payload(payload, dt_val)
            delta = None if previous_temp is None else temp_float - previous_temp

            try:
                estimation = self._calculator.interpolate_estimation(temp_float)
            except ValueError as err:
                raise ForecastEnergyCalculationError(
                    "no_data_for_approximation",
                    {"temperature": str(temp_float)},
                ) from err

            energy_kwh = float(estimation["power_overall_w"]) / 1000.0
            trend_adjustment = None
            if delta is not None:
                trend_adjustment = self._calculator.trend_adjustment(delta, temp_float)
                energy_kwh *= trend_adjustment

            total_energy_kwh += energy_kwh
            hours.append(
                ForecastHourEnergy(
                    datetime=dt_val,
                    temperature=temp_float,
                    temperature_delta=delta,
                    trend_adjustment=trend_adjustment,
                    energy_kwh=energy_kwh,
                    confidence=str(estimation["confidence"]),
                    approximated=bool(estimation["approximated"]),
                    approximation_source=estimation.get("approximation_source"),
                )
            )
            previous_temp = temp_float

        return ForecastEnergyResult(
            total_energy_kwh=total_energy_kwh,
            hours=hours,
            hours_requested=hours_ahead,
            starting_hour=starting_hour,
        )

    def _parse_forecast(
        self, forecast: list[dict[str, Any]], now: datetime
    ) -> list[tuple[datetime, dict[str, Any]]]:
        parsed_forecast: list[tuple[datetime, dict[str, Any]]] = []
        for item in forecast:
            dt_val = self._parse_datetime(item.get("datetime")) if isinstance(item, dict) else None
            if dt_val is None:
                continue
            parsed_forecast.append((self._as_local(dt_val, now), item))
        parsed_forecast.sort(key=lambda pair: pair[0])
        return parsed_forecast

    def _find_start_index(
        self,
        parsed_forecast: list[tuple[datetime, dict[str, Any]]],
        now: datetime,
        starting_hour: int,
    ) -> int:
        for idx, (dt_val, _) in enumerate(parsed_forecast):
            if dt_val >= now and dt_val.hour == starting_hour:
                return idx
        raise ForecastEnergyCalculationError("forecast_window_too_small")

    def _previous_temperature(
        self,
        parsed_forecast: list[tuple[datetime, dict[str, Any]]],
        start_index: int,
        now: datetime,
        current_temperature: float | None,
    ) -> float | None:
        window_start_dt = parsed_forecast[start_index][0]
        next_hour_start = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

        if window_start_dt == next_hour_start:
            return current_temperature

        if start_index == 0:
            raise ForecastEnergyCalculationError("forecast_window_too_small")

        prev_dt, prev_payload = parsed_forecast[start_index - 1]
        return self._temperature_from_payload(prev_payload, prev_dt)

    @staticmethod
    def _temperature_from_payload(payload: dict[str, Any], dt_val: datetime) -> float:
        temperature = payload.get("temperature")
        if temperature is None:
            raise ForecastEnergyCalculationError(
                "forecast_hour_missing",
                {"datetime": dt_val.isoformat()},
            )

        try:
            return float(temperature)
        except (TypeError, ValueError) as err:
            raise ForecastEnergyCalculationError(
                "forecast_hour_missing",
                {"datetime": dt_val.isoformat()},
            ) from err

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _as_local(dt_val: datetime, now: datetime) -> datetime:
        if dt_val.tzinfo is None:
            return dt_val.replace(tzinfo=now.tzinfo)
        if now.tzinfo is None:
            return dt_val.replace(tzinfo=None)
        return dt_val.astimezone(now.tzinfo)
