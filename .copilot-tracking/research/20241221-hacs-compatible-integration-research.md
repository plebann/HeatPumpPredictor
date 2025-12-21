<!-- markdownlint-disable-file -->
# Task Research Notes: Home Assistant Custom Integration with HACS Compatibility

## Research Executed

### External Documentation
- #fetch:"https://developers.home-assistant.io/docs/creating_integration_manifest"
  - Complete manifest.json specification with all required and optional fields
  - Integration types: device, entity, hardware, helper, hub, service, system, virtual
  - Config flow requirements and single_config_entry option
  - Dependencies and after_dependencies patterns
  - Discovery methods: Bluetooth, Zeroconf, SSDP, HomeKit, MQTT, DHCP, USB
  
- #fetch:"https://hacs.xyz/docs/publish/integration"
  - HACS-specific repository structure requirements
  - Validation rules for manifest.json
  - hacs.json optional configuration file
  - Home Assistant Brands registration requirement
  - GitHub releases best practices

- #fetch:"https://developers.home-assistant.io/docs/config_entries_index"
  - Config entry lifecycle: not loaded → setup in progress → loaded → unloaded
  - async_setup_entry and async_unload_entry implementation patterns
  - async_forward_entry_setups for platform setup
  - Config entry migration patterns
  
- #fetch:"https://developers.home-assistant.io/docs/core/entity"
  - Base Entity class properties and lifecycle hooks
  - Entity naming with has_entity_name=True (mandatory for new integrations)
  - Property implementation: @property methods, _attr_ attributes, entity descriptions
  - Update patterns: polling vs. subscription
  - Entity registry and device registry integration

- #fetch:"https://developers.home-assistant.io/docs/development_testing"
  - pytest testing framework patterns
  - async_setup_component and MockConfigEntry for testing
  - Snapshot testing with syrupy
  - Code coverage requirements

### GitHub Repository Analysis
- #githubRepo:"hacs/integration hacs.json validation repository structure requirements manifest"
  - HACS validates repositories using ValidationManager
  - HacsManifest class structure with fields: content_in_root, country, filename, hacs, homeassistant, etc.
  - Integration-specific validation in HacsIntegrationRepository
  - manifest.json must include: domain, documentation, issue_tracker, codeowners, name, version
  - Repository structure must be: custom_components/<domain>/__init__.py, manifest.json, etc.

## Key Discoveries

### Home Assistant Custom Integration Structure

A Home Assistant custom integration is a Python package that extends Home Assistant functionality. For HACS compatibility, it must follow specific structure and conventions:

**Required Directory Structure:**
```
repository_root/
├── custom_components/
│   └── <your_domain>/
│       ├── __init__.py          # Integration initialization
│       ├── manifest.json        # Integration metadata (REQUIRED)
│       ├── config_flow.py       # UI configuration flow (if config_flow: true)
│       ├── strings.json         # Translations
│       ├── sensor.py            # Platform implementation (example)
│       ├── binary_sensor.py     # Platform implementation (example)
│       └── const.py             # Constants
├── README.md                     # Documentation (REQUIRED)
├── hacs.json                     # HACS-specific config (OPTIONAL)
└── .github/
    └── workflows/                # CI/CD (recommended)
```

**Alternative Structure (with content_in_root: true in hacs.json):**
```
repository_root/
├── __init__.py
├── manifest.json
├── config_flow.py
├── strings.json
└── ...
```

### manifest.json Requirements

**Mandatory Fields for HACS:**
```json
{
  "domain": "your_integration",
  "name": "Your Integration Name",
  "codeowners": ["@github_username"],
  "documentation": "https://github.com/username/repo",
  "issue_tracker": "https://github.com/username/repo/issues",
  "requirements": ["library==1.0.0"],
  "version": "1.0.0",
  "config_flow": true,
  "integration_type": "hub",
  "iot_class": "cloud_polling"
}
```

**Field Specifications:**

- **domain**: Unique identifier (lowercase, underscores allowed, must match directory name)
- **name**: Human-readable integration name
- **version**: REQUIRED for custom integrations (SemVer or CalVer via AwesomeVersion)
- **codeowners**: GitHub usernames responsible for the integration
- **documentation**: URL to integration documentation
- **issue_tracker**: URL to GitHub issues page
- **integration_type**: One of: device, entity, hardware, helper, hub, service, system, virtual
- **iot_class**: One of: assumed_state, cloud_polling, cloud_push, local_polling, local_push, calculated
- **config_flow**: Boolean - if true, must have config_flow.py
- **single_config_entry**: Boolean - limits to one config entry
- **requirements**: List of PyPI packages with versions
- **dependencies**: List of Home Assistant integrations to load first
- **after_dependencies**: List of optional integrations to load before if configured

### HACS-Specific Requirements

**Home Assistant Brands Registration:**
Integration must be added to https://github.com/home-assistant/brands repository for proper UI integration and logo display.

**Optional hacs.json Configuration:**
```json
{
  "name": "My Integration",
  "content_in_root": false,
  "filename": "custom_file.js",
  "country": ["US", "CA"],
  "homeassistant": "2023.1.0",
  "hacs": "1.30.0",
  "render_readme": true,
  "zip_release": false,
  "persistent_directory": "userdata"
}
```

**hacs.json Schema (from HACS source):**
- **name**: Override integration name (required)
- **content_in_root**: Boolean - files in repo root vs custom_components/ subdirectory
- **filename**: Specific file to use (for plugins/themes)
- **country**: List of country codes or single string
- **homeassistant**: Minimum Home Assistant version required
- **hacs**: Minimum HACS version required
- **render_readme**: Boolean - render README as info
- **zip_release**: Boolean - use release assets instead of repository files
- **persistent_directory**: Directory that persists across updates
- **hide_default_branch**: Boolean - hide default branch in version selection

**Repository Validation Rules:**
1. Must have README.md or info.md file
2. Must have repository description
3. Must have topics/tags on GitHub
4. Must have issues enabled
5. Repository must not be archived
6. Integration manifest.json must pass schema validation
7. For integrations: domain, documentation, issue_tracker, codeowners, name, version required

### Integration Implementation Patterns

**1. __init__.py Structure:**
```python
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    # Initialize your client/coordinator
    # Store in hass.data[DOMAIN][entry.entry_id]
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
```

**2. Config Flow Pattern (config_flow.py):**
```python
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol

class MyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""
    
    VERSION = 1
    
    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            # Validate input
            # Create entry
            return self.async_create_entry(
                title=user_input["name"],
                data=user_input
            )
        
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("host"): str,
                vol.Required("api_key"): str,
            }),
            errors=errors
        )
```

**3. Entity Platform Pattern (sensor.py):**
```python
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    async_add_entities([
        MySensorEntity(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    ])

class MySensorEntity(SensorEntity):
    """Representation of a sensor."""
    
    _attr_has_entity_name = True  # MANDATORY for new integrations
    
    def __init__(self, coordinator, description: SensorEntityDescription):
        """Initialize the sensor."""
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"
        self._attr_device_info = coordinator.device_info
```

**4. Entity Naming Convention (MANDATORY):**
- Set `_attr_has_entity_name = True` on all entities
- If entity is main feature: `_attr_name = None` (uses device name)
- If entity is additional feature: use `translation_key` or `_attr_name`
- Entity friendly_name format: "{device_name} {entity_name}" or just "{device_name}"

**5. Data Coordinator Pattern (recommended for polling):**
```python
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity

class MyCoordinator(DataUpdateCoordinator):
    """Coordinator to manage data updates."""
    
    def __init__(self, hass, client):
        """Initialize coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.client = client
    
    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            return await self.client.get_data()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")
```

### Testing Best Practices

**Test Structure:**
```python
# tests/conftest.py - Fixtures
@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={"host": "test.local", "api_key": "test"},
        unique_id="test-unique-id",
    )

# tests/test_init.py - Integration tests
async def test_setup_entry(hass, mock_config_entry):
    """Test setting up entry."""
    mock_config_entry.add_to_hass(hass)
    
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    
    assert mock_config_entry.state == ConfigEntryState.LOADED

# tests/test_sensor.py - Platform tests
async def test_sensor_state(hass, mock_config_entry):
    """Test sensor state."""
    state = hass.states.get("sensor.device_temperature")
    assert state
    assert state.state == "23.5"
```

**Key Testing Patterns:**
- Use `async_setup_component()` or `hass.config_entries.async_setup()` to set up
- Assert via `hass.states.get()` not direct entity access
- Use `MockConfigEntry` from tests/common.py
- Test via service calls using `hass.services.async_call()`
- Use snapshot testing for complex outputs (entity states, registry entries)

### Code Quality Requirements

**Integration Quality Scale:**
New integrations must meet at least Bronze tier:
- Uses config flow (no YAML configuration)
- Has tests covering setup and basic functionality
- Uses unique_id for entities
- Follows entity naming conventions (has_entity_name=True)
- Has proper error handling

**Linting Requirements:**
- Uses `ruff` for code formatting and linting
- Uses `pylint` for additional checks
- Must pass `pre-commit` hooks before committing
- Run `pre-commit run --all-files` before PR

### GitHub Releases and Versioning

**Version Management:**
- Use SemVer (1.0.0) or CalVer format
- Version must be in manifest.json for custom integrations
- Recommended: Use GitHub releases with tags (v1.0.0)
- HACS will show last 5 releases + default branch in UI

**Release Assets (optional):**
- If using zip_release: true in hacs.json, must provide filename
- Release assets used instead of repository files
- Useful for compiled/bundled integrations

## Recommended Approach

Based on research, here's the optimal structure for a HACS-compatible Home Assistant custom integration:

### Project Structure
```
HeatPumpPredictor/
├── custom_components/
│   └── heat_pump_predictor/
│       ├── __init__.py
│       ├── manifest.json
│       ├── config_flow.py
│       ├── const.py
│       ├── coordinator.py
│       ├── sensor.py
│       ├── binary_sensor.py
│       ├── strings.json
│       ├── translations/
│       │   └── en.json
│       └── icons.json (optional)
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_*.py
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── release.yml
├── README.md
├── LICENSE
├── hacs.json (optional)
├── .gitignore
└── requirements_dev.txt
```

### Core Implementation Files

**1. manifest.json - Complete specification:**
```json
{
  "domain": "heat_pump_predictor",
  "name": "Heat Pump Predictor",
  "codeowners": ["@mpleb"],
  "config_flow": true,
  "documentation": "https://github.com/mpleb/HeatPumpPredictor",
  "integration_type": "hub",
  "iot_class": "cloud_polling",
  "issue_tracker": "https://github.com/mpleb/HeatPumpPredictor/issues",
  "requirements": [],
  "version": "1.0.0"
}
```

**2. __init__.py - Integration entry point:**
- Implement `async_setup_entry(hass, entry)` 
- Implement `async_unload_entry(hass, entry)`
- Forward setup to platforms using `async_forward_entry_setups()`
- Store coordinator/client in `hass.data[DOMAIN][entry.entry_id]`

**3. config_flow.py - UI configuration:**
- Subclass `config_entries.ConfigFlow`
- Set `domain = DOMAIN`
- Implement `async_step_user()` for initial setup
- Add validation and error handling
- Return `FlowResult` with `async_create_entry()` or `async_show_form()`

**4. coordinator.py - Data management:**
- Use `DataUpdateCoordinator` for polling integrations
- Centralize API calls and error handling
- Set appropriate `update_interval`

**5. Platform files (sensor.py, etc.) - Entity implementation:**
- Implement `async_setup_entry()` function
- Create entity classes inheriting from platform base (SensorEntity, etc.)
- Set `_attr_has_entity_name = True` on all entities
- Use `entity_description` pattern for multiple similar entities
- Implement device_info for device registry integration

### Development Workflow

1. **Initial Setup:**
   - Create repository with required structure
   - Create manifest.json with all required fields
   - Add README.md with clear documentation
   - Add LICENSE file

2. **Implementation:**
   - Start with __init__.py and config_flow.py
   - Add coordinator if polling needed
   - Implement platforms one at a time
   - Add translations in strings.json

3. **Testing:**
   - Write tests in tests/ directory
   - Run `pytest tests/` locally
   - Ensure tests cover setup, unload, and entity states
   - Use `pytest --cov` for coverage reports

4. **Quality Checks:**
   - Run `pre-commit run --all-files`
   - Fix any linting errors
   - Ensure Bronze tier quality scale compliance

5. **HACS Preparation:**
   - Register in Home Assistant Brands repository
   - Add repository description and topics on GitHub
   - Enable issues on repository
   - Create first release with tag (v1.0.0)
   - Optionally add hacs.json for customization

6. **Publishing:**
   - Submit to HACS default repository via PR to hacs/default
   - Or document as custom repository for users

## Implementation Guidance

### Objectives
- Create a production-ready Home Assistant custom integration
- Ensure full HACS compatibility for easy user installation
- Follow all Home Assistant best practices and conventions
- Implement proper config flow for UI-based setup
- Support entity registry and device registry
- Provide comprehensive testing

### Key Tasks
1. Define integration domain and structure
2. Create manifest.json with complete metadata
3. Implement config flow for user setup
4. Create data coordinator for API/data management
5. Implement entity platforms (sensor, binary_sensor, etc.)
6. Add proper device and entity registration
7. Implement translations (strings.json, translations/)
8. Write comprehensive tests
9. Set up CI/CD with GitHub Actions
10. Register with Home Assistant Brands
11. Create documentation (README.md)
12. Publish first release

### Dependencies
- Home Assistant core (for development: home-assistant/core)
- pytest and pytest-homeassistant-custom-component for testing
- Python libraries for hardware/API integration
- pre-commit for code quality

### Success Criteria
- Integration loads without errors in Home Assistant
- Config flow works and creates config entries
- Entities appear in Home Assistant with proper naming
- Tests pass with good coverage
- Passes all linting checks
- HACS validation succeeds
- Installation via HACS works seamlessly
- Meets Integration Quality Scale Bronze tier minimum
