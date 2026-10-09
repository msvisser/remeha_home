"""Diagnostics support for Remeha Home."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {
    "token",
    "access_token",
    "refresh_token",
    "id_token",
    "auth_implementation",
    "email",
    "houseName",
    "name",
    "serialNumber",
    "macAddress",
    "ipAddress",
    "latitude",
    "longitude",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return the dashboard, technical and consumption data the coordinator holds."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "dashboard": async_redact_data(coordinator.data or {}, TO_REDACT),
        "technical_info": async_redact_data(coordinator.technical_info, TO_REDACT),
        "consumption_data": async_redact_data(
            coordinator.appliance_consumption_data, TO_REDACT
        ),
        "last_consumption_response": async_redact_data(
            getattr(coordinator, "last_consumption_response", {}), TO_REDACT
        ),
    }
