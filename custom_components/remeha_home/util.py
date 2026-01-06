"""Utility helpers for the Remeha Home integration."""

from __future__ import annotations


def detect_dhw_setpoint_activity(
    target: float | None,
    comfort: float | None,
    reduced: float | None,
    tolerance: float = 0.25,
) -> str | None:
    """Return 'Comfort', 'Eco', or None based on which setpoint matches the target."""
    if (
        comfort is not None
        and target is not None
        and abs(target - comfort) < tolerance
    ):
        return "Comfort"

    if (
        reduced is not None
        and target is not None
        and abs(target - reduced) < tolerance
    ):
        return "Eco"

    return None
