"""Sensor platform setup for Heat Pump Predictor integration."""
from __future__ import annotations

import logging
from typing import Iterable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_WEATHER_ENTITY, DOMAIN
from .coordinator import HeatPumpCoordinator
from .sensors import (
    HeatPumpForecastSensor,
    HeatPumpPerformanceCurveSensor,
    HeatPumpSensorBase,
    ScheduledForecastEnergySensor,
    build_bucket_sensors,
)

_LOGGER = logging.getLogger(__name__)


def _resolve_weather_entity(hass: HomeAssistant, entry: ConfigEntry) -> str | None:
    """Resolve the weather entity to use, with a safe fallback for legacy entries."""
    if weather_entity := entry.options.get(CONF_WEATHER_ENTITY) or entry.data.get(CONF_WEATHER_ENTITY):
        return weather_entity

    weather_entities = hass.states.async_entity_ids("weather")
    if len(weather_entities) == 1:
        fallback = weather_entities[0]
        _LOGGER.warning(
            "Weather entity not configured; falling back to detected weather entity: %s",
            fallback,
        )
        return fallback

    _LOGGER.error(
        "Weather entity not configured and auto-detect failed; re-run the config flow to select a weather entity"
    )
    return None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: HeatPumpCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[HeatPumpSensorBase] = list(_build_bucket_entities(coordinator))

    weather_entity = _resolve_weather_entity(hass, entry)
    if weather_entity:
        entities.append(HeatPumpForecastSensor(hass, coordinator, weather_entity))

    entities.extend(
        _build_scheduled_forecast_entities(hass, coordinator)
    )

    entities.extend(
        [
            HeatPumpPerformanceCurveSensor(coordinator, "power_curve", "performance_power_curve"),
            HeatPumpPerformanceCurveSensor(coordinator, "duty_cycle_curve", "performance_duty_cycle_curve"),
            HeatPumpPerformanceCurveSensor(coordinator, "energy_distribution", "performance_energy_distribution"),
        ]
    )

    async_add_entities(entities)
    _LOGGER.info("Created %d heat pump predictor sensors", len(entities))


def _build_bucket_entities(coordinator: HeatPumpCoordinator) -> Iterable[HeatPumpSensorBase]:
    """Helper to build all bucket sensors."""
    return build_bucket_sensors(coordinator)


def _build_scheduled_forecast_entities(
    hass: HomeAssistant, coordinator: HeatPumpCoordinator
) -> Iterable[ScheduledForecastEnergySensor]:
    """Create scheduled forecast energy sensors."""

    schedules = [
        {
            "unique_id": "scheduled_forecast_6_00",
            "translation_key": "scheduled_forecast_morning",
            "schedule": (4, 0, 0),
            "starting_hour": 6,
            "hours_ahead": 7,
        },
        {
            "unique_id": "scheduled_forecast_15_00",
            "translation_key": "scheduled_forecast_afternoon",
            "schedule": (13, 0, 0),
            "starting_hour": 15,
            "hours_ahead": 7,
        },
        {
            "unique_id": "scheduled_forecast_daily",
            "translation_key": "scheduled_forecast_daily",
            "schedule": (23, 55, 0),
            "starting_hour": 0,
            "hours_ahead": 24,
        },
    ]

    for item in schedules:
        hour, minute, second = item["schedule"]
        yield ScheduledForecastEnergySensor(
            hass,
            coordinator,
            unique_id=item["unique_id"],
            translation_key=item["translation_key"],
            schedule_hour=hour,
            schedule_minute=minute,
            schedule_second=second,
            starting_hour=item["starting_hour"],
            hours_ahead=item["hours_ahead"],
        )
