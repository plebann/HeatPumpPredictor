# Python Conventions for Home Assistant Integrations

## Language Version
- Target Python 3.12+ (Home Assistant current requirement)
- Use modern Python features (dataclasses, type hints, etc.)

## Import Organization

```python
from __future__ import annotations  # Always first

# Standard library imports
import asyncio
import logging
from datetime import timedelta
from typing import Any, Callable

# Third-party imports (Home Assistant core)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

# Local application imports
from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    LOGGER,
)
```

## Type Hints

### Function Signatures
```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up from config entry."""
    ...

async def async_get_data(self) -> dict[str, Any]:
    """Fetch data from API."""
    ...

def calculate_efficiency(
    temp_in: float,
    temp_out: float,
) -> float | None:
    """Calculate efficiency, returns None if invalid."""
    ...
```

### Class Properties
```python
class MyEntity(SensorEntity):
    """My entity class."""
    
    _attr_has_entity_name: bool = True
    _attr_native_value: float | None = None
    
    @property
    def native_value(self) -> float | None:
        """Return the state."""
        return self._attr_native_value
```

### Collections
```python
# Python 3.9+ style (preferred)
from collections.abc import Callable

config_data: dict[str, Any]
sensor_list: list[SensorEntity]
config_map: dict[str, list[str]]
callback_fn: Callable[[str], None]

# Generic types
from typing import TypeVar
T = TypeVar("T")

def get_first(items: list[T]) -> T | None:
    """Get first item or None."""
    return items[0] if items else None
```

## Async Patterns

### Always Use Async for I/O
```python
# ✅ Correct
async def async_update(self) -> None:
    """Update data."""
    self._data = await self.client.fetch_data()

# ❌ Wrong - blocks event loop
def update(self) -> None:
    """Update data."""
    self._data = self.client.fetch_data()  # Synchronous I/O
```

### Async Context Managers
```python
async def async_connect(self) -> None:
    """Connect to device."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
```

### Callbacks
```python
from homeassistant.core import callback

@callback
def _handle_coordinator_update(self) -> None:
    """Handle updated data from coordinator."""
    # Callback decorator ensures this runs in event loop
    self.async_write_ha_state()
```

## Error Handling

### Specific Exception Handling
```python
from homeassistant.exceptions import HomeAssistantError

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(HomeAssistantError):
    """Error to indicate invalid authentication."""

try:
    await client.authenticate(api_key)
except TimeoutError as err:
    raise CannotConnect("Timeout connecting to device") from err
except AuthError as err:
    raise InvalidAuth("Invalid API key") from err
```

### Coordinator Error Handling
```python
from homeassistant.helpers.update_coordinator import UpdateFailed

async def _async_update_data(self) -> dict[str, Any]:
    """Fetch data from API."""
    try:
        return await self.api.get_data()
    except ApiConnectionError as err:
        raise UpdateFailed(f"Error communicating with API: {err}") from err
```

### Never Swallow Exceptions
```python
# ✅ Correct - re-raise or handle properly
try:
    await risky_operation()
except ValueError as err:
    _LOGGER.error("Operation failed: %s", err)
    raise

# ❌ Wrong - loses error information
try:
    await risky_operation()
except Exception:
    pass
```

## Dataclasses

### Entity Descriptions
```python
from dataclasses import dataclass
from typing import Callable

@dataclass(frozen=True, kw_only=True)
class MyEntityDescription(SensorEntityDescription):
    """Describes a sensor entity."""
    
    value_fn: Callable[[dict[str, Any]], Any] | None = None
    available_fn: Callable[[dict[str, Any]], bool] = lambda _: True

# Usage
SENSORS = (
    MyEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["temp"],
    ),
)
```

### Config Data
```python
from dataclasses import dataclass

@dataclass
class DeviceConfig:
    """Device configuration."""
    
    host: str
    api_key: str
    scan_interval: timedelta = timedelta(seconds=30)
```

## Logging

```python
import logging

_LOGGER = logging.getLogger(__name__)

# Different log levels
_LOGGER.debug("Detailed debug info: %s", debug_data)
_LOGGER.info("Integration setup complete")
_LOGGER.warning("Deprecated API used: %s", api_version)
_LOGGER.error("Failed to fetch data: %s", error)
_LOGGER.exception("Unexpected error occurred")  # Includes traceback
```

### Lazy Formatting
```python
# ✅ Correct - lazy evaluation
_LOGGER.debug("Processing %s items: %s", len(items), items)

# ❌ Wrong - formats even if debug disabled
_LOGGER.debug(f"Processing {len(items)} items: {items}")
```

## Constants

### Organize in const.py
```python
"""Constants for Heat Pump Predictor integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "heat_pump_predictor"
LOGGER = logging.getLogger(__package__)

# Configuration
CONF_API_KEY: Final = "api_key"
CONF_DEVICE_ID: Final = "device_id"

# Defaults
DEFAULT_NAME: Final = "Heat Pump"
DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=30)
DEFAULT_TIMEOUT: Final = 10

# Platforms
PLATFORMS: Final = [Platform.SENSOR, Platform.BINARY_SENSOR]

# Attributes
ATTR_TEMPERATURE: Final = "temperature"
ATTR_POWER: Final = "power"
```

## Property Patterns

### Class Attributes (Preferred)
```python
class MySensor(SensorEntity):
    """Sensor using class attributes."""
    
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
```

### Property Methods (When Dynamic)
```python
class MySensor(SensorEntity):
    """Sensor with dynamic properties."""
    
    _attr_has_entity_name = True
    
    @property
    def native_value(self) -> float | None:
        """Return current temperature."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("temperature")
    
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
        )
```

## Docstrings

### Module Level
```python
"""Support for Heat Pump sensors.

This module provides sensor entities for monitoring heat pump status,
including temperature, power consumption, and efficiency metrics.
"""
```

### Class Level
```python
class HeatPumpSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Heat Pump sensor.
    
    This sensor monitors various metrics from the heat pump device
    and updates automatically via the coordinator.
    """
```

### Function Level
```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heat Pump sensors from a config entry.
    
    Args:
        hass: Home Assistant instance.
        entry: Config entry for this integration.
        async_add_entities: Callback to add entities.
    """
```

## Context Managers and Cleanup

### Async Lifecycle Hooks
```python
class MyEntity(SensorEntity):
    """Entity with proper cleanup."""
    
    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        # Subscribe to updates
        self._unsubscribe = self.device.subscribe(
            self._handle_update
        )
        # Register cleanup
        self.async_on_remove(self._unsubscribe)
    
    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed."""
        # Additional cleanup if needed
        if self._connection:
            await self._connection.close()
```

## List Comprehensions and Generators

```python
# ✅ List comprehension for entity creation
entities = [
    HeatPumpSensor(coordinator, description)
    for description in SENSOR_DESCRIPTIONS
]

# ✅ Generator expression for filtering
active_entities = (
    entity for entity in entities
    if entity.available
)

# ✅ Dictionary comprehension
sensor_map = {
    desc.key: desc
    for desc in SENSOR_DESCRIPTIONS
}
```

## F-strings vs % formatting

```python
# ✅ f-strings for general code
error_msg = f"Failed to connect to {host}:{port}"

# ✅ % formatting for logging (lazy evaluation)
_LOGGER.error("Failed to connect to %s:%s", host, port)

# ✅ f-strings for entity IDs
unique_id = f"{device_id}_{sensor_type}"
```

## Avoid Common Pitfalls

```python
# ❌ Don't use mutable default arguments
def process(data: list[str] = []):  # Wrong!
    ...

# ✅ Use None and create in function
def process(data: list[str] | None = None) -> None:
    """Process data."""
    if data is None:
        data = []
    ...

# ❌ Don't compare with is for values
if status is "online":  # Wrong!
    ...

# ✅ Use == for value comparison
if status == "online":
    ...

# ❌ Don't use bare except
try:
    risky()
except:  # Wrong!
    pass

# ✅ Catch specific exceptions
try:
    risky()
except (ValueError, KeyError) as err:
    _LOGGER.error("Error: %s", err)
```
