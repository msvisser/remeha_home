"""On-demand, read-only energy-history action for a Remeha appliance."""

from __future__ import annotations

from datetime import date, datetime
import logging

from aiohttp import ClientError
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
import voluptuous as vol

from .const import DOMAIN
from .energy_history import combine_history, history_batches

_LOGGER = logging.getLogger(__name__)

SERVICE_GET_ENERGY_HISTORY = "get_energy_history"


def _date(value) -> date:
    """Accept the ISO date that Home Assistant's date selector sends."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise vol.Invalid("Expected an ISO date (YYYY-MM-DD)") from exc
    raise vol.Invalid("Expected an ISO date (YYYY-MM-DD)")


SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("start_date"): _date,
        vol.Required("end_date"): _date,
    }
)


def _appliance_for_device(hass: HomeAssistant, device_id: str) -> tuple[str, object]:
    """Resolve a parent appliance from its device, zone or producer device.

    A hybrid heat-pump and boiler may both have instanceWithinDevice=1; never
    use producer identifiers to determine which energy data should be returned.
    """
    registry = dr.async_get(hass)
    device = registry.async_get(device_id)
    seen = set()

    while device and device.id not in seen:
        seen.add(device.id)
        for domain, identifier in device.identifiers:
            if domain != DOMAIN:
                continue
            for entry_data in hass.data.get(DOMAIN, {}).values():
                coordinator = entry_data["coordinator"]
                if coordinator.data and any(
                    appliance.get("applianceId") == identifier
                    for appliance in coordinator.data.get("appliances", [])
                ):
                    return identifier, entry_data["api"]
        device = (
            registry.async_get(device.via_device_id) if device.via_device_id else None
        )

    raise HomeAssistantError("Select an appliance or producer from Remeha Home")


def async_register_energy_history_service(hass: HomeAssistant) -> None:
    """Register once, independently of the number of Remeha config entries."""

    async def async_get_energy_history(call: ServiceCall) -> ServiceResponse:
        start, end = call.data["start_date"], call.data["end_date"]
        try:
            batches = list(history_batches(start, end))
        except ValueError as exc:
            raise HomeAssistantError(str(exc)) from exc

        appliance_id, api = _appliance_for_device(hass, call.data["device_id"])
        responses = []
        for batch_start, batch_end in batches:
            try:
                responses.append(
                    await api.async_get_consumption_data_for_range(
                        appliance_id, batch_start, batch_end
                    )
                )
            except (ClientError, TimeoutError) as exc:
                _LOGGER.warning("Remeha energy-history request failed: %s", exc)
                raise HomeAssistantError(
                    "Remeha Home could not retrieve energy history; retry later"
                ) from exc

        try:
            result = combine_history(start, end, responses)
        except (TypeError, ValueError) as exc:
            raise HomeAssistantError(f"Invalid Remeha history response: {exc}") from exc

        # Do not persist old values in HA's recorder or publish states.
        return {"appliance_id": appliance_id, **result}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_ENERGY_HISTORY,
        async_get_energy_history,
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
