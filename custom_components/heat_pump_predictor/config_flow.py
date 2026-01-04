"""Config flow for Heat Pump Predictor integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_ENERGY_SENSOR,
    CONF_RUNNING_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_CURRENT_TEMPERATURE_SENSOR,
    CONF_WEATHER_ENTITY,
)

_LOGGER = logging.getLogger(__name__)


class HeatPumpPredictorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Heat Pump Predictor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_ENERGY_SENSOR]}_{user_input[CONF_TEMPERATURE_SENSOR]}"
            )
            self._abort_if_unique_id_configured()

            try:
                await self._validate_input(user_input)
                return self.async_create_entry(
                    title="Heat Pump Predictor",
                    data=user_input,
                )
            except ValueError as err:
                _LOGGER.error("Validation failed: %s", err)
                errors["base"] = "invalid_entity"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ENERGY_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                            device_class=SensorDeviceClass.ENERGY,
                        )
                    ),
                    vol.Required(CONF_RUNNING_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="binary_sensor")
                    ),
                    vol.Required(CONF_TEMPERATURE_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                            device_class=SensorDeviceClass.TEMPERATURE,
                        )
                    ),
                    vol.Required(CONF_CURRENT_TEMPERATURE_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                            device_class=SensorDeviceClass.TEMPERATURE,
                        )
                    ),
                    vol.Required(CONF_WEATHER_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="weather")
                    ),
                }
            ),
            errors=errors,
        )

    async def _validate_input(self, user_input: dict[str, Any]) -> None:
        """Validate user input."""
        energy_state = self.hass.states.get(user_input[CONF_ENERGY_SENSOR])
        running_state = self.hass.states.get(user_input[CONF_RUNNING_SENSOR])
        temp_state = self.hass.states.get(user_input[CONF_TEMPERATURE_SENSOR])
        current_temp_state = self.hass.states.get(user_input[CONF_CURRENT_TEMPERATURE_SENSOR])
        weather_state = self.hass.states.get(user_input[CONF_WEATHER_ENTITY])

        if energy_state is None:
            raise ValueError(f"Energy sensor {user_input[CONF_ENERGY_SENSOR]} not found")
        if running_state is None:
            raise ValueError(f"Running sensor {user_input[CONF_RUNNING_SENSOR]} not found")
        if temp_state is None:
            raise ValueError(f"Temperature sensor {user_input[CONF_TEMPERATURE_SENSOR]} not found")
        if current_temp_state is None:
            raise ValueError(f"Current temperature sensor {user_input[CONF_CURRENT_TEMPERATURE_SENSOR]} not found")
        if weather_state is None:
            raise ValueError(f"Weather entity {user_input[CONF_WEATHER_ENTITY]} not found")

        try:
            float(energy_state.state)
        except (ValueError, TypeError) as err:
            raise ValueError("Energy sensor must have numeric value") from err

        try:
            float(temp_state.state)
        except (ValueError, TypeError) as err:
            raise ValueError("Temperature sensor must have numeric value") from err

        try:
            float(current_temp_state.state)
        except (ValueError, TypeError) as err:
            raise ValueError("Current temperature sensor must have numeric value") from err

        if running_state.state not in ("on", "off"):
            raise ValueError("Running sensor must be a binary sensor (on/off)")


class HeatPumpPredictorOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow to reconfigure weather entity."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._errors: dict[str, str] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle options flow start."""
        self._errors = {}

        if user_input is not None:
            weather_state = self.hass.states.get(user_input[CONF_WEATHER_ENTITY])
            if weather_state is None:
                self._errors["base"] = "invalid_entity"
            else:
                return self.async_create_entry(title="Heat Pump Predictor options", data=user_input)

        current_weather = (
            self.config_entry.options.get(CONF_WEATHER_ENTITY)
            or self.config_entry.data.get(CONF_WEATHER_ENTITY)
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_WEATHER_ENTITY,
                        default=current_weather,
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="weather")
                    ),
                }
            ),
            errors=self._errors,
        )


async def async_get_options_flow(
    config_entry: config_entries.ConfigEntry,
) -> HeatPumpPredictorOptionsFlow:
    """Get the options flow handler."""

    return HeatPumpPredictorOptionsFlow(config_entry)