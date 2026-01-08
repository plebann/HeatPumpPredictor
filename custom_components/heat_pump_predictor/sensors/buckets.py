"""Bucket-based sensors for Heat Pump Predictor."""
from __future__ import annotations

from typing import Iterable

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

from ..const import (
    MAX_TEMP,
    MIN_TEMP,
    TRANSLATION_KEY_AVG_POWER_OVERALL,
    TRANSLATION_KEY_AVG_POWER_RUNNING,
    TRANSLATION_KEY_DUTY_CYCLE,
    TRANSLATION_KEY_ENERGY,
)
from ..data_manager import TemperatureBucketData
from ..coordinator import HeatPumpCoordinator
from .base import HeatPumpSensorBase, HeatPumpSensorEntityDescription


class HeatPumpEnergySensor(HeatPumpSensorBase[HeatPumpSensorEntityDescription]):
    """Total energy per bucket."""

    @property
    def native_value(self) -> float | None:
        bucket = self._get_bucket()
        return None if not bucket or not self.entity_description.value_fn else self.entity_description.value_fn(bucket)


class HeatPumpPowerRunningSensor(HeatPumpSensorBase[HeatPumpSensorEntityDescription]):
    """Average running power per bucket."""

    @property
    def native_value(self) -> float | None:
        bucket = self._get_bucket()
        return None if not bucket or not self.entity_description.value_fn else self.entity_description.value_fn(bucket)


class HeatPumpPowerOverallSensor(HeatPumpSensorBase[HeatPumpSensorEntityDescription]):
    """Average overall power per bucket."""

    @property
    def native_value(self) -> float | None:
        bucket = self._get_bucket()
        return None if not bucket or not self.entity_description.value_fn else self.entity_description.value_fn(bucket)


class HeatPumpDutyCycleSensor(HeatPumpSensorBase[HeatPumpSensorEntityDescription]):
    """Duty cycle per bucket."""

    @property
    def native_value(self) -> float | None:
        bucket = self._get_bucket()
        return None if not bucket or not self.entity_description.value_fn else self.entity_description.value_fn(bucket)


def build_bucket_sensors(coordinator: HeatPumpCoordinator) -> Iterable[HeatPumpSensorBase]:
    """Create all bucket sensors for the configured temperature range."""

    for temp in range(MIN_TEMP, MAX_TEMP + 1):
        yield HeatPumpEnergySensor(
            coordinator,
            HeatPumpSensorEntityDescription(
                key=f"total_energy_{temp}",
                translation_key=TRANSLATION_KEY_ENERGY,
                translation_placeholders={"temperature": str(temp)},
                bucket_temp=temp,
                device_class=SensorDeviceClass.ENERGY,
                native_unit_of_measurement="kWh",
                state_class=SensorStateClass.TOTAL_INCREASING,
                entity_registry_enabled_default=False,
                icon="mdi:lightning-bolt",
                value_fn=lambda data: data.total_energy_kwh,
            ),
        )

        yield HeatPumpPowerRunningSensor(
            coordinator,
            HeatPumpSensorEntityDescription(
                key=f"avg_power_running_{temp}",
                translation_key=TRANSLATION_KEY_AVG_POWER_RUNNING,
                translation_placeholders={"temperature": str(temp)},
                bucket_temp=temp,
                device_class=SensorDeviceClass.POWER,
                native_unit_of_measurement="W",
                state_class=SensorStateClass.MEASUREMENT,
                entity_registry_enabled_default=False,
                icon="mdi:flash",
                value_fn=lambda data: data.average_power_when_running,
            ),
        )

        yield HeatPumpPowerOverallSensor(
            coordinator,
            HeatPumpSensorEntityDescription(
                key=f"avg_power_overall_{temp}",
                translation_key=TRANSLATION_KEY_AVG_POWER_OVERALL,
                translation_placeholders={"temperature": str(temp)},
                bucket_temp=temp,
                device_class=SensorDeviceClass.POWER,
                native_unit_of_measurement="W",
                state_class=SensorStateClass.MEASUREMENT,
                entity_registry_enabled_default=False,
                icon="mdi:flash",
                value_fn=lambda data: data.average_power_overall,
            ),
        )

        yield HeatPumpDutyCycleSensor(
            coordinator,
            HeatPumpSensorEntityDescription(
                key=f"duty_cycle_{temp}",
                translation_key=TRANSLATION_KEY_DUTY_CYCLE,
                translation_placeholders={"temperature": str(temp)},
                bucket_temp=temp,
                native_unit_of_measurement="%",
                state_class=SensorStateClass.MEASUREMENT,
                suggested_display_precision=2,
                entity_registry_enabled_default=False,
                icon="mdi:percent",
                value_fn=lambda data: data.duty_cycle_percent,
            ),
        )