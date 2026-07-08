"""Data manager for Heat Pump Predictor integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
import math

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


@dataclass
class TemperatureBucketData:
    """Data for a single temperature bucket."""
    
    temperature: int
    total_energy_kwh: float
    total_time_seconds: float
    running_time_seconds: float
    last_update: datetime | None
    
    @property
    def average_power_when_running(self) -> float:
        """Calculate average power when heat pump is running (W)."""
        if self.running_time_seconds == 0:
            return 0.0
        hours = self.running_time_seconds / 3600
        return (self.total_energy_kwh * 1000) / hours if hours > 0 else 0.0
    
    @property
    def average_power_overall(self) -> float:
        """Calculate average power overall (includes off time) (W)."""
        if self.total_time_seconds == 0:
            return 0.0
        hours = self.total_time_seconds / 3600
        return (self.total_energy_kwh * 1000) / hours if hours > 0 else 0.0
    
    @property
    def duty_cycle_percent(self) -> float:
        """Calculate duty cycle percentage."""
        if self.total_time_seconds == 0:
            return 0.0
        return (self.running_time_seconds / self.total_time_seconds) * 100


class HeatPumpDataManager:
    """Manage heat pump data across temperature buckets."""
    
    def __init__(self) -> None:
        """Initialize the data manager."""
        self.buckets: dict[int, TemperatureBucketData] = {}
        
        # Track previous state for delta calculations
        self._last_temperature: float | None = None
        self._last_energy_kwh: float | None = None
        self._last_running_state: bool | None = None
        self._last_update_time: datetime | None = None
    
    def get_bucket(self, temperature: float) -> int:
        """Get bucket index for temperature using floor function."""
        return int(math.floor(temperature))

    def get_or_create_bucket(self, temperature: float) -> TemperatureBucketData:
        """Return existing bucket data, creating it if needed."""
        bucket_temp = self.get_bucket(temperature)
        if bucket_temp not in self.buckets:
            self.buckets[bucket_temp] = TemperatureBucketData(bucket_temp, 0.0, 0.0, 0.0, None)
        return self.buckets[bucket_temp]

    @property
    def observed_bucket_temperatures(self) -> list[int]:
        """Return bucket temperatures that have observed time, sorted ascending."""
        return sorted(
            temp
            for temp, bucket in self.buckets.items()
            if bucket.total_time_seconds > 0
        )

    @property
    def observed_temperature_span(self) -> tuple[int, int] | None:
        """Return lowest and highest bucket temperatures with observed time."""
        observed_temps = self.observed_bucket_temperatures
        if not observed_temps:
            return None
        return observed_temps[0], observed_temps[-1]

    @property
    def service_prediction_range(self) -> tuple[int, int] | None:
        """Return inclusive manual service prediction range, if history exists."""
        observed_span = self.observed_temperature_span
        if observed_span is None:
            return None
        lowest_bucket, highest_bucket = observed_span
        return lowest_bucket - 5, highest_bucket + 5

    def is_within_service_prediction_range(self, temperature: float) -> bool:
        """Return whether temperature is inside the manual service range."""
        prediction_range = self.service_prediction_range
        if prediction_range is None:
            return False
        lower_bound, upper_bound = prediction_range
        return lower_bound <= temperature <= upper_bound
    
    def process_state_update(
        self,
        current_temp: float,
        current_energy_kwh: float,
        is_running: bool,
        timestamp: datetime,
    ) -> int | None:
        """Process state update with previous-state attribution logic."""
        # First update - initialize tracking
        if self._last_update_time is None:
            self._last_update_time = timestamp
            self._last_temperature = current_temp
            self._last_energy_kwh = current_energy_kwh
            self._last_running_state = is_running
            _LOGGER.debug("Initialized tracking with temp=%.1f°C, energy=%.2f kWh", 
                         current_temp, current_energy_kwh)
            return None
        
        # Calculate deltas
        time_delta_seconds = (timestamp - self._last_update_time).total_seconds()
        energy_delta_kwh = current_energy_kwh - self._last_energy_kwh
        
        # Validate deltas
        if time_delta_seconds <= 0:
            _LOGGER.warning("Invalid time delta: %s seconds", time_delta_seconds)
            return None
        
        if energy_delta_kwh < 0:
            _LOGGER.warning("Energy counter decreased: %.2f -> %.2f kWh",
                          self._last_energy_kwh, current_energy_kwh)
            # Counter reset - update tracking and return
            self._last_energy_kwh = current_energy_kwh
            return None
        
        # CRITICAL: Attribute to PREVIOUS bucket (where we WERE)
        bucket_temp = self.get_bucket(self._last_temperature)
        bucket = self.get_or_create_bucket(self._last_temperature)
        had_observed_time = bucket.total_time_seconds > 0
        
        # Update bucket data
        bucket.total_time_seconds += time_delta_seconds
        
        # Always add energy if consumed (includes water pump, standby, etc.)
        if energy_delta_kwh > 0:
            bucket.total_energy_kwh += energy_delta_kwh
        
        # Only count running time when heat pump is actively running
        if self._last_running_state:
            bucket.running_time_seconds += time_delta_seconds
            _LOGGER.debug("Updated bucket %d°C: +%.2f kWh, +%.1f s running",
                         bucket_temp, energy_delta_kwh, time_delta_seconds)
        elif energy_delta_kwh > 0:
            _LOGGER.debug("Updated bucket %d°C: +%.2f kWh (idle consumption)",
                         bucket_temp, energy_delta_kwh)
        
        bucket.last_update = timestamp
        
        # Update tracking for next iteration
        self._last_temperature = current_temp
        self._last_energy_kwh = current_energy_kwh
        self._last_running_state = is_running
        self._last_update_time = timestamp

        return bucket_temp if not had_observed_time and bucket.total_time_seconds > 0 else None
    
    def to_dict(self) -> dict:
        """Serialize buckets to dictionary for storage."""
        return {
            "buckets": {
                str(temp): {
                    "temperature": bucket.temperature,
                    "total_energy_kwh": bucket.total_energy_kwh,
                    "total_time_seconds": bucket.total_time_seconds,
                    "running_time_seconds": bucket.running_time_seconds,
                    "last_update": bucket.last_update.isoformat() if bucket.last_update else None,
                }
                for temp, bucket in self.buckets.items()
            },
            "tracking": {
                "last_temperature": self._last_temperature,
                "last_energy_kwh": self._last_energy_kwh,
                "last_running_state": self._last_running_state,
                "last_update_time": self._last_update_time.isoformat() if self._last_update_time else None,
            }
        }
    
    def from_dict(self, data: dict) -> None:
        """Restore buckets from dictionary."""
        # Handle both old format (flat dict) and new format (with buckets key)
        buckets_data = data.get("buckets", data)
        
        for temp_str, bucket_data in buckets_data.items():
            temp = int(temp_str)
            last_update = None
            if bucket_data.get("last_update"):
                last_update = datetime.fromisoformat(bucket_data["last_update"])

            self.buckets[temp] = TemperatureBucketData(
                temperature=bucket_data["temperature"],
                total_energy_kwh=bucket_data["total_energy_kwh"],
                total_time_seconds=bucket_data["total_time_seconds"],
                running_time_seconds=bucket_data["running_time_seconds"],
                last_update=last_update,
            )
        
        # Restore tracking state (critical for correct delta calculations after restart)
        if "tracking" in data:
            tracking = data["tracking"]
            self._last_temperature = tracking.get("last_temperature")
            self._last_energy_kwh = tracking.get("last_energy_kwh")
            self._last_running_state = tracking.get("last_running_state")
            if tracking.get("last_update_time"):
                self._last_update_time = datetime.fromisoformat(tracking["last_update_time"])
            _LOGGER.info("Restored tracking state: temp=%.1f°C, energy=%.2f kWh", 
                        self._last_temperature or 0, self._last_energy_kwh or 0)
        
        _LOGGER.info("Restored %d temperature buckets from storage", len(buckets_data))