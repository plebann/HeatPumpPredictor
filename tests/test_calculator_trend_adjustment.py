"""Tests for calculator trend adjustment scaling."""
from __future__ import annotations

import pytest

from custom_components.heat_pump_predictor.calculator import HeatPumpCalculator


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (0.0, 1.0),
        (-1.0, 1.1),
        (-3.0, 1.3),
        (-5.0, 1.4),
        (1.0, 0.85),
        (3.0, 0.55),
        (4.0, 0.5),
    ],
)
def test_trend_adjustment_scaling_and_caps(delta: float, expected: float) -> None:
    """Return expected multiplier for cooling/warming deltas with caps."""
    assert HeatPumpCalculator.trend_adjustment(delta) == pytest.approx(expected)
