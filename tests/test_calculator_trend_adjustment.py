"""Tests for calculator trend adjustment scaling."""
from __future__ import annotations

import pytest

from custom_components.heat_pump_predictor.calculator import HeatPumpCalculator


@pytest.mark.parametrize(
    ("delta", "temperature", "expected"),
    [
        (0.0, 10.0, 1.0),
        (-1.0, 10.0, 1.1),
        (-3.0, 10.0, 1.3),
        (-5.0, 10.0, 1.4),
        (1.0, 10.0, 0.85),
        (3.0, 10.0, 0.55),
        (4.0, 10.0, 0.5),
        (-3.0, 20.0, 1.0),
        (3.0, 20.0, 1.0),
        (1.0, 25.0, 1.1),
        (3.0, 25.0, 1.3),
        (5.0, 25.0, 1.4),
        (-1.0, 25.0, 0.85),
        (-3.0, 25.0, 0.55),
        (-4.0, 25.0, 0.5),
    ],
)
def test_trend_adjustment_scaling_and_caps(
    delta: float, temperature: float, expected: float
) -> None:
    """Return expected multiplier for operating-zone trend adjustments."""
    assert HeatPumpCalculator.trend_adjustment(delta, temperature) == pytest.approx(expected)
