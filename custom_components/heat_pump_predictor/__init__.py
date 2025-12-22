"""The Heat Pump Predictor integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_TEMPERATURE,
    DOMAIN,
    MAX_TEMP,
    MIN_TEMP,
    SERVICE_CALCULATE_ENERGY,
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


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Heat Pump Predictor integration."""
    
    async def async_calculate_energy(call: ServiceCall) -> ServiceResponse:
        """Calculate energy consumption for given temperature."""
        temperature: float = call.data[ATTR_TEMPERATURE]
        config_entry_id: str | None = call.data.get(ATTR_CONFIG_ENTRY_ID)
        
        # Get coordinator
        coordinator = _get_coordinator_for_service(hass, config_entry_id)
        
        # Get temperature bucket
        bucket_index = coordinator.data_manager.get_bucket(temperature)
        bucket_data = coordinator.data_manager.buckets[bucket_index]
        
        # Check if we have data - approximate if needed
        is_approximated = False
        approximation_source = None
        
        if bucket_data.total_time_seconds == 0:
            # Find bucket closest to 0°C that has data
            source_bucket_index = None
            min_distance = float('inf')
            
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
                    translation_placeholders={
                        "temperature": str(temperature),
                    },
                )
            
            # Use source bucket and calculate temperature-based multiplier
            source_bucket_data = coordinator.data_manager.buckets[source_bucket_index]
            is_approximated = True
            approximation_source = source_bucket_index
            
            # Calculate multiplier based on temperature zones
            MIDPOINT = 25  # Temperature where usage is minimal
            source_temp = source_bucket_index
            target_temp = temperature
            
            if target_temp <= MIDPOINT:
                # Heating zone (0-25°C): usage decreases as temp increases
                temp_diff = target_temp - source_temp
                multiplier = max(0.1, 1.0 - (0.20 * temp_diff))
            else:
                # Cooling zone (>25°C): first decrease to midpoint, then increase
                # Calculate what power would be at midpoint
                temp_diff_to_midpoint = MIDPOINT - source_temp
                multiplier_at_midpoint = max(0.1, 1.0 - (0.20 * temp_diff_to_midpoint))
                
                # Then increase from midpoint
                temp_diff_from_midpoint = target_temp - MIDPOINT
                multiplier = multiplier_at_midpoint * (1.0 + (0.20 * temp_diff_from_midpoint))
            
            # Apply multiplier to power values
            power_overall = source_bucket_data.average_power_overall * multiplier
            power_running = source_bucket_data.average_power_when_running * multiplier
            duty_cycle = source_bucket_data.duty_cycle_percent
            data_hours = source_bucket_data.total_time_seconds / 3600
        else:
            # Use actual bucket data
            power_overall = bucket_data.average_power_overall
            power_running = bucket_data.average_power_when_running
            duty_cycle = bucket_data.duty_cycle_percent
            data_hours = bucket_data.total_time_seconds / 3600
        
        # Calculate energy for 1 hour
        energy_kwh = power_overall / 1000.0
        
        # Calculate confidence
        if is_approximated:
            confidence = "approximated"
        else:
            confidence = _calculate_confidence(bucket_data.total_time_seconds)
        
        # Build response
        return {
            "energy_kwh": round(energy_kwh, 3),
            "power_running_w": round(power_running, 1),
            "power_overall_w": round(power_overall, 1),
            "duty_cycle_percent": round(duty_cycle, 2),
            "temperature_bucket": bucket_index,
            "confidence": confidence,
            "approximated": is_approximated,
            "approximation_source": approximation_source,
            "data_points_hours": round(data_hours, 2),
        }
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_CALCULATE_ENERGY,
        async_calculate_energy,
        schema=SERVICE_CALCULATE_ENERGY_SCHEMA,
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