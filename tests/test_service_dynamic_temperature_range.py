"""Tests for manual service temperature range behavior."""
from __future__ import annotations

import pytest
import voluptuous as vol

from custom_components.heat_pump_predictor import SERVICE_CALCULATE_ENERGY_SCHEMA
from custom_components.heat_pump_predictor.const import ATTR_TEMPERATURE


def test_calculate_energy_schema_accepts_temperatures_outside_old_fixed_range() -> None:
    """Leave dynamic service prediction range validation to runtime history."""
    validated = SERVICE_CALCULATE_ENERGY_SCHEMA({ATTR_TEMPERATURE: 48.2})

    assert validated[ATTR_TEMPERATURE] == 48.2


@pytest.mark.parametrize("temperature", [-25.1, 30.1])
def test_calculate_energy_schema_no_longer_rejects_old_range_boundaries(temperature: float) -> None:
    """Do not keep the historical static supported range in the service schema."""
    try:
        SERVICE_CALCULATE_ENERGY_SCHEMA({ATTR_TEMPERATURE: temperature})
    except vol.Invalid as err:  # pragma: no cover - failure path assertion clarity
        pytest.fail(f"schema should not reject {temperature}: {err}")
