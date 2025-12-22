"""Data manager for Heat Pump Predictor integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
import math

from homeassistant.util import dt as dt_util

from .const import MIN_TEMP, MAX_TEMP

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
        # 56 buckets from -25 to 30
        self.buckets: dict[int, TemperatureBucketData] = {
            temp: TemperatureBucketData(temp, 0.0, 0.0, 0.0, None)
            for temp in range(MIN_TEMP, MAX_TEMP + 1)
        }
        
        # Track previous state for delta calculations
        self._last_temperature: float | None = None
        self._last_energy_kwh: float | None = None
        self._last_running_state: bool | None = None
        self._last_update_time: datetime | None = None
    
    def get_bucket(self, temperature: float) -> int:
        """Get bucket index for temperature using floor function."""
        temp_int = int(math.floor(temperature))
        # Clamp to range [-25, 30]
        return max(MIN_TEMP, min(MAX_TEMP, temp_int))
    
    def process_state_update(
        self,
        current_temp: float,
        current_energy_kwh: float,
        is_running: bool,
        timestamp: datetime,
    ) -> None:
        """Process state update with previous-state attribution logic."""
        # First update - initialize tracking
        if self._last_update_time is None:
            self._last_update_time = timestamp
            self._last_temperature = current_temp
            self._last_energy_kwh = current_energy_kwh
            self._last_running_state = is_running
            _LOGGER.debug("Initialized tracking with temp=%.1f°C, energy=%.2f kWh", 
                         current_temp, current_energy_kwh)
            return
        
        # Calculate deltas
        time_delta_seconds = (timestamp - self._last_update_time).total_seconds()
        energy_delta_kwh = current_energy_kwh - self._last_energy_kwh
        
        # Validate deltas
        if time_delta_seconds <= 0:
            _LOGGER.warning("Invalid time delta: %s seconds", time_delta_seconds)
            return
        
        if energy_delta_kwh < 0:
            _LOGGER.warning("Energy counter decreased: %.2f -> %.2f kWh",
                          self._last_energy_kwh, current_energy_kwh)
            # Counter reset - update tracking and return
            self._last_energy_kwh = current_energy_kwh
            return
        
        # CRITICAL: Attribute to PREVIOUS bucket (where we WERE)
        bucket_temp = self.get_bucket(self._last_temperature)
        bucket = self.buckets[bucket_temp]
        
        # Update bucket data
        bucket.total_time_seconds += time_delta_seconds
        
        if self._last_running_state and energy_delta_kwh > 0:
            bucket.running_time_seconds += time_delta_seconds
            bucket.total_energy_kwh += energy_delta_kwh
            _LOGGER.debug("Updated bucket %d°C: +%.2f kWh, +%.1f s running",
                         bucket_temp, energy_delta_kwh, time_delta_seconds)
        
        bucket.last_update = timestamp
        
        # Update tracking for next iteration
        self._last_temperature = current_temp
        self._last_energy_kwh = current_energy_kwh
        self._last_running_state = is_running
        self._last_update_time = timestamp