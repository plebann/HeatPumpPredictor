"""The Heat Pump Predictor integration."""
from __future__ import annotations

import logging
import math

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_TEMPERATURE,
    DOMAIN,
    MAX_TEMP,
    MIN_TEMP,
    SERVICE_CALCULATE_ENERGY,
    SERVICE_CALCULATE_FORECAST_ENERGY,
    ATTR_STARTING_HOUR,
    ATTR_HOURS_AHEAD,
    CONF_TEMPERATURE_SENSOR,
)
from .coordinator import HeatPumpCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

# Service schema
SERVICE_CALCULATE_ENERGY_SCHEMA = vol.Schema({
    vol.Required(ATTR_TEMPERATURE): vol.All(
        vol.Coerce(float),
        vol.Range(min=MIN_TEMP, max=MAX_TEMP)
    ),
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
})

SERVICE_CALCULATE_FORECAST_ENERGY_SCHEMA = vol.Schema({
    vol.Required(ATTR_STARTING_HOUR): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
    vol.Required(ATTR_HOURS_AHEAD): vol.All(vol.Coerce(int), vol.Range(min=1, max=48)),
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
})


def _get_coordinator_for_service(
    hass: HomeAssistant, config_entry_id: str | None
) -> HeatPumpCoordinator:
    """Get coordinator for service call."""
    if not hass.data.get(DOMAIN):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="integration_not_setup",
        )
    
    # If config_entry_id provided, use it
    if config_entry_id:
        if config_entry_id not in hass.data[DOMAIN]:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_config_entry",
                translation_placeholders={"config_entry": config_entry_id},
            )
        return hass.data[DOMAIN][config_entry_id]
    
    # Auto-detect if only one entry exists
    coordinators = hass.data[DOMAIN]
    if len(coordinators) == 0:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="integration_not_setup",
        )
    if len(coordinators) > 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="multiple_config_entries",
        )
    
    # Return the single coordinator
    return next(iter(coordinators.values()))


def _calculate_confidence(total_time_seconds: float) -> str:
    """Calculate confidence level based on data quantity."""
    hours = total_time_seconds / 3600
    if hours >= 24:
        return "high"
    if hours >= 4:
        return "medium"
    return "low"


def _estimate_power_for_temperature(
    coordinator: HeatPumpCoordinator, temperature: float
) -> dict[str, float | int | str | bool | None]:
    """Estimate power metrics for a given temperature bucket (with approximation fallback)."""
    bucket_index = coordinator.data_manager.get_bucket(temperature)
    bucket_data = coordinator.data_manager.buckets[bucket_index]

    is_approximated = False
    approximation_source = None

    if bucket_data.total_time_seconds == 0:
        source_bucket_index = None
        min_distance = float("inf")

        for temp in range(MIN_TEMP, MAX_TEMP + 1):
            if coordinator.data_manager.buckets[temp].total_time_seconds > 0:
                distance = abs(temp - 0)
                if distance < min_distance:
                    min_distance = distance
                    source_bucket_index = temp

        if source_bucket_index is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_data_for_approximation",
                translation_placeholders={"temperature": str(temperature)},
            )

        source_bucket_data = coordinator.data_manager.buckets[source_bucket_index]
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

    confidence = "approximated" if is_approximated else _calculate_confidence(bucket_data.total_time_seconds)

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


def _combine_confidence(conf_a: str, conf_b: str, approximated: bool) -> str:
    """Combine two confidence labels conservatively."""
    if approximated:
        return "approximated"
    if "low" in (conf_a, conf_b):
        return "low"
    if "medium" in (conf_a, conf_b):
        return "medium"
    return "high"


def _interpolate_estimation(
    coordinator: HeatPumpCoordinator, temperature: float
) -> dict[str, float | int | str | bool | None]:
    """Estimate power for fractional temperatures via linear interpolation."""
    lower = max(MIN_TEMP, min(MAX_TEMP, math.floor(temperature)))
    upper = max(MIN_TEMP, min(MAX_TEMP, math.ceil(temperature)))

    if lower == upper:
        return _estimate_power_for_temperature(coordinator, float(temperature))

    lower_est = _estimate_power_for_temperature(coordinator, float(lower))
    upper_est = _estimate_power_for_temperature(coordinator, float(upper))
    weight = (temperature - lower) / (upper - lower)

    def _lerp(a: float, b: float, w: float) -> float:
        return a + (b - a) * w

    approximated = bool(lower_est["approximated"] or upper_est["approximated"])
    confidence = _combine_confidence(
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


def _trend_adjustment(delta: float) -> float:
    """Calculate adjustment factor based on hour-to-hour temperature delta."""
    if delta == 0:
        return 1.0

    ratio = min(1.0, abs(delta) / 1.5)
    factor = 0.20 * ratio
    if delta < 0:
        return 1.0 + factor  # getting colder -> more energy
    return max(0.0, 1.0 - factor)  # getting warmer -> less energy


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Heat Pump Predictor integration."""
    
    async def async_calculate_energy(call: ServiceCall) -> ServiceResponse:
        """Calculate energy consumption for given temperature."""
        temperature: float = call.data[ATTR_TEMPERATURE]
        config_entry_id: str | None = call.data.get(ATTR_CONFIG_ENTRY_ID)
        
        # Get coordinator
        coordinator = _get_coordinator_for_service(hass, config_entry_id)
        
        estimation = _estimate_power_for_temperature(coordinator, temperature)

        energy_kwh = estimation["power_overall_w"] / 1000.0

        return {
            "energy_kwh": round(energy_kwh, 3),
            "power_running_w": round(estimation["power_running_w"], 1),
            "power_overall_w": round(estimation["power_overall_w"], 1),
            "duty_cycle_percent": round(estimation["duty_cycle_percent"], 2),
            "temperature_bucket": estimation["temperature_bucket"],
            "confidence": estimation["confidence"],
            "approximated": estimation["approximated"],
            "approximation_source": estimation["approximation_source"],
            "data_points_hours": round(estimation["data_points_hours"], 2),
        }

    async def async_calculate_forecast_energy(call: ServiceCall) -> ServiceResponse:
        """Calculate energy consumption for a forecast window."""

        starting_hour: int = call.data[ATTR_STARTING_HOUR]
        hours_ahead: int = call.data[ATTR_HOURS_AHEAD]
        config_entry_id: str | None = call.data.get(ATTR_CONFIG_ENTRY_ID)

        coordinator = _get_coordinator_for_service(hass, config_entry_id)

        current_temp_entity = coordinator.config_entry.data.get(CONF_TEMPERATURE_SENSOR)
        current_temp_state = hass.states.get(current_temp_entity) if current_temp_entity else None
        current_temperature: float | None = None
        if current_temp_state:
            try:
                current_temperature = float(current_temp_state.state)
            except (TypeError, ValueError):
                current_temperature = None

        if not coordinator.hourly_forecast:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="forecast_unavailable",
            )

        now_local = dt_util.as_local(dt_util.utcnow())
        parsed_forecast: list[tuple[object, dict]] = []
        for item in coordinator.hourly_forecast:
            dt_val = dt_util.parse_datetime(item.get("datetime")) if isinstance(item, dict) else None
            if dt_val is None:
                continue
            parsed_forecast.append((dt_util.as_local(dt_val), item))

        parsed_forecast.sort(key=lambda pair: pair[0])

        start_indexes = [idx for idx, (dt_val, _) in enumerate(parsed_forecast) if dt_val >= now_local and dt_val.hour == starting_hour]
        if not start_indexes:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="forecast_window_too_small",
            )

        start_index = start_indexes[0]
        window = parsed_forecast[start_index : start_index + hours_ahead]

        if len(window) < hours_ahead:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="forecast_window_too_small",
            )

        total_energy_kwh = 0.0
        hour_details: list[dict[str, object]] = []
        approximated_hours = 0

        previous_temp: float | None = current_temperature

        for dt_val, payload in window:
            temperature = payload.get("temperature") if isinstance(payload, dict) else None
            if temperature is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="forecast_hour_missing",
                    translation_placeholders={"datetime": dt_val.isoformat()},
                )

            temp_float = float(temperature)
            estimation = _interpolate_estimation(coordinator, temp_float)

            delta = None
            if previous_temp is not None:
                delta = temp_float - previous_temp

            energy_kwh = estimation["power_overall_w"] / 1000.0
            if delta is not None:
                energy_kwh *= _trend_adjustment(delta)

            total_energy_kwh += energy_kwh
            approximated_hours += 1 if estimation["approximated"] else 0

            hour_details.append(
                {
                    "datetime": dt_val.isoformat(),
                    "temperature": temp_float,
                    "temperature_delta": delta,
                    "trend_adjustment": None if delta is None else _trend_adjustment(delta),
                    "energy_kwh": round(energy_kwh, 3),
                    "confidence": estimation["confidence"],
                    "approximated": estimation["approximated"],
                    "approximation_source": estimation["approximation_source"],
                }
            )

            previous_temp = temp_float

        return {
            "total_energy_kwh": round(total_energy_kwh, 3),
            "hours": hour_details,
            "hours_requested": hours_ahead,
            "hours_returned": len(hour_details),
            "approximated_hours": approximated_hours,
            "starting_hour": starting_hour,
        }
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_CALCULATE_ENERGY,
        async_calculate_energy,
        schema=SERVICE_CALCULATE_ENERGY_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CALCULATE_FORECAST_ENERGY,
        async_calculate_forecast_energy,
        schema=SERVICE_CALCULATE_FORECAST_ENERGY_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Heat Pump Predictor from a config entry."""
    _LOGGER.debug("Setting up Heat Pump Predictor integration")
    
    # Initialize coordinator
    coordinator = HeatPumpCoordinator(hass, entry)
    await coordinator.async_setup()
    
    # Store coordinator in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Forward setup to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Set up services (call once, not per entry)
    if not hass.services.has_service(DOMAIN, SERVICE_CALCULATE_ENERGY):
        async_setup_services(hass)
    
    _LOGGER.info("Heat Pump Predictor setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Heat Pump Predictor integration")
    
    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Cleanup coordinator
        coordinator: HeatPumpCoordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_shutdown()
        
        # Clean up hass.data
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
        
        _LOGGER.info("Heat Pump Predictor unloaded successfully")
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)