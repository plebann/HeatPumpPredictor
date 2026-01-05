"""Sensor base classes for Heat Pump Predictor."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription

from ..shared_base import HeatPumpBaseEntity
from ..data_manager import TemperatureBucketData

BucketValueFn = Callable[[TemperatureBucketData], float | None]


@dataclass
class HeatPumpSensorEntityDescription(SensorEntityDescription):
    """Extended description for heat pump sensors."""

    value_fn: BucketValueFn | None = None
    bucket_temp: int | None = None


TDescription = TypeVar("TDescription", bound=HeatPumpSensorEntityDescription)


class HeatPumpSensorBase(HeatPumpBaseEntity, SensorEntity, Generic[TDescription]):
    """Base sensor that wires coordinator, device info, and translations."""

    entity_description: TDescription

    def __init__(self, coordinator, description: TDescription) -> None:
        super().__init__(coordinator, description.key, translation_key=description.translation_key)
        self.entity_description = description

    def _get_bucket(self) -> TemperatureBucketData | None:
        """Return bucket data for the described temperature, if any."""
        if self.entity_description.bucket_temp is None:
            return None
        return self.coordinator.data_manager.buckets.get(self.entity_description.bucket_temp)