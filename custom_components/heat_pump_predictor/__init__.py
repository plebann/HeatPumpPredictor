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


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Heat Pump Predictor integration."""
    
    async def async_calculate_energy(call: ServiceCall) -> ServiceResponse:
        """Calculate energy consumption for given temperature."""
        temperature: float = call.data[ATTR_TEMPERATURE]
        config_entry_id: str | None = call.data.get(ATTR_CONFIG_ENTRY_ID)
        
        # Get coordinator
        coordinator = _get_coordinator_for_service(hass, config_entry_id)
        
        try:
            estimation = coordinator.calculator.estimate_power_for_temperature(temperature)
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_data_for_approximation",
                translation_placeholders={"temperature": str(temperature)},
            ) from err

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

        return await coordinator.async_calculate_forecast_energy(
            starting_hour=starting_hour,
            hours_ahead=hours_ahead,
            current_temperature=current_temperature,
        )
    
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

    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
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


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by reloading the config entry."""
    await hass.config_entries.async_reload(entry.entry_id)