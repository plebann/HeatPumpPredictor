"""Calculation utilities for Heat Pump Predictor."""
from __future__ import annotations

import math
from typing import Any

from .const import MAX_TEMP, MIN_TEMP
from .data_manager import HeatPumpDataManager, TemperatureBucketData


class HeatPumpCalculator:
    """Provide estimation helpers for energy and power calculations."""

    def __init__(self, data_manager: HeatPumpDataManager) -> None:
        """Initialize calculator with shared data manager."""
        self._data_manager = data_manager

    def estimate_power_for_temperature(self, temperature: float) -> dict[str, Any]:
        """Estimate bucketed power metrics for a given temperature."""
        bucket_index = self._data_manager.get_bucket(temperature)
        bucket_data = self._data_manager.buckets[bucket_index]

        is_approximated = False
        approximation_source = None

        if bucket_data.total_time_seconds == 0:
            source_bucket_index = None
            min_distance = float("inf")

            for temp in range(MIN_TEMP, MAX_TEMP + 1):
                if self._data_manager.buckets[temp].total_time_seconds > 0:
                    distance = abs(temp - temperature)
                    if distance < min_distance:
                        min_distance = distance
                        source_bucket_index = temp

            if source_bucket_index is None:
                raise ValueError(f"No data available to approximate temperature {temperature}")

            source_bucket_data = self._data_manager.buckets[source_bucket_index]
            is_approximated = True
            approximation_source = source_bucket_index

            midpoint = 25  # Temperature where usage is minimal
            source_temp = source_bucket_index
            target_temp = temperature

            if target_temp <= midpoint:
                temp_diff = target_temp - source_temp
                multiplier = max(0.1, 1.0 - (0.20 * temp_diff))
            else:
                temp_diff_to_midpoint = midpoint - source_temp
                multiplier_at_midpoint = max(0.1, 1.0 - (0.20 * temp_diff_to_midpoint))
                temp_diff_from_midpoint = target_temp - midpoint
                multiplier = multiplier_at_midpoint * (1.0 + (0.20 * temp_diff_from_midpoint))

            power_overall = source_bucket_data.average_power_overall * multiplier
            power_running = source_bucket_data.average_power_when_running * multiplier
            duty_cycle = source_bucket_data.duty_cycle_percent
            data_hours = source_bucket_data.total_time_seconds / 3600
        else:
            power_overall = bucket_data.average_power_overall
            power_running = bucket_data.average_power_when_running
            duty_cycle = bucket_data.duty_cycle_percent
            data_hours = bucket_data.total_time_seconds / 3600

        confidence = "approximated" if is_approximated else self._calculate_confidence(bucket_data)

        return {
            "power_overall_w": power_overall,
            "power_running_w": power_running,
            "duty_cycle_percent": duty_cycle,
            "temperature_bucket": bucket_index,
            "confidence": confidence,
            "approximated": is_approximated,
            "approximation_source": approximation_source,
            "data_points_hours": data_hours,
        }

    def interpolate_estimation(self, temperature: float) -> dict[str, Any]:
        """Estimate power for fractional temperatures via linear interpolation."""
        lower = max(MIN_TEMP, min(MAX_TEMP, math.floor(temperature)))
        upper = max(MIN_TEMP, min(MAX_TEMP, math.ceil(temperature)))

        if lower == upper:
            return self.estimate_power_for_temperature(float(temperature))

        lower_est = self.estimate_power_for_temperature(float(lower))
        upper_est = self.estimate_power_for_temperature(float(upper))
        weight = (temperature - lower) / (upper - lower)

        def _lerp(a: float, b: float, w: float) -> float:
            return a + (b - a) * w

        approximated = bool(lower_est["approximated"] or upper_est["approximated"])
        confidence = self._combine_confidence(
            str(lower_est["confidence"]), str(upper_est["confidence"]), approximated
        )

        return {
            "power_overall_w": _lerp(float(lower_est["power_overall_w"]), float(upper_est["power_overall_w"]), weight),
            "power_running_w": _lerp(float(lower_est["power_running_w"]), float(upper_est["power_running_w"]), weight),
            "duty_cycle_percent": _lerp(float(lower_est["duty_cycle_percent"]), float(upper_est["duty_cycle_percent"]), weight),
            "temperature_bucket": temperature,
            "confidence": confidence,
            "approximated": approximated,
            "approximation_source": lower_est.get("approximation_source") or upper_est.get("approximation_source"),
            "data_points_hours": min(
                float(lower_est.get("data_points_hours", 0.0)),
                float(upper_est.get("data_points_hours", 0.0)),
            ),
        }

    @staticmethod
    def trend_adjustment(delta: float) -> float:
        """Calculate adjustment factor based on hour-to-hour temperature delta."""
        if delta == 0:
            return 1.0

        ratio = min(1.0, abs(delta) / 1.5)
        factor = 0.20 * ratio
        if delta < 0:
            return 1.0 + factor  # getting colder -> more energy
        return max(0.0, 1.0 - factor)  # getting warmer -> less energy

    @staticmethod
    def _combine_confidence(conf_a: str, conf_b: str, approximated: bool) -> str:
        if approximated:
            return "approximated"
        if "low" in (conf_a, conf_b):
            return "low"
        if "medium" in (conf_a, conf_b):
            return "medium"
        return "high"

    @staticmethod
    def _calculate_confidence(bucket_data: TemperatureBucketData) -> str:
        hours = bucket_data.total_time_seconds / 3600
        if hours >= 24:
            return "high"
        if hours >= 4:
            return "medium"
        return "low"