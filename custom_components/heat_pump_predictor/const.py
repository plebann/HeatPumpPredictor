"""Constants for the Heat Pump Predictor integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "heat_pump_predictor"

# Temperature range constants
MIN_TEMP = -25
MAX_TEMP = 30

# Update interval (5 minutes)
UPDATE_INTERVAL = timedelta(minutes=5)

# Configuration keys
CONF_ENERGY_SENSOR = "energy_sensor"
CONF_RUNNING_SENSOR = "running_sensor"
CONF_TEMPERATURE_SENSOR = "temperature_sensor"
CONF_CURRENT_TEMPERATURE_SENSOR = "current_temperature_sensor"
CONF_WEATHER_ENTITY = "weather_entity"

# Entity translation keys
TRANSLATION_KEY_ENERGY = "total_energy"
TRANSLATION_KEY_AVG_POWER_RUNNING = "avg_power_running"
TRANSLATION_KEY_AVG_POWER_OVERALL = "avg_power_overall"
TRANSLATION_KEY_DUTY_CYCLE = "duty_cycle"

# Service names
SERVICE_CALCULATE_ENERGY = "calculate_energy"
SERVICE_CALCULATE_FORECAST_ENERGY = "calculate_forecast_energy"

# Service attributes
ATTR_TEMPERATURE = "temperature"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_STARTING_HOUR = "starting_hour"
ATTR_HOURS_AHEAD = "hours_ahead"
