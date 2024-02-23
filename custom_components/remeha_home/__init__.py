"""The Remeha Home integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RemehaHomeOAuth2Implementation, RemehaHomeAPI
from .config_flow import RemehaHomeLoginFlowHandler
from .const import DOMAIN
from .coordinator import RemehaHomeUpdateCoordinator
from .coordinator import RemehaHomeUpdatePowerCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Remeha Home."""
    hass.data.setdefault(DOMAIN, {})

    RemehaHomeLoginFlowHandler.async_register_implementation(
        hass,
        RemehaHomeOAuth2Implementation(async_get_clientsession(hass)),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Remeha Home from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    oauth_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    api = RemehaHomeAPI(oauth_session)
    coordinator = RemehaHomeUpdateCoordinator(hass, api)
    power_coordinator = RemehaHomeUpdatePowerCoordinator(hass, api)

    await coordinator.async_config_entry_first_refresh()
    await power_coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "power_coordinator": power_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
