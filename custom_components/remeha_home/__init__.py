"""The Remeha Home integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .api import RemehaHomeOAuth2Implementation, RemehaHomeAPI
from .config_flow import RemehaHomeLoginFlowHandler
from .const import DOMAIN
from .coordinator import RemehaHomeUpdateCoordinator
from .energy_history_service import async_register_energy_history_service
from .holiday import STORAGE_VERSION, HolidayModeRestorer, storage_key
from .producer_ids import ProducerIdResolver

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]


def producer_ids_storage_key(entry: ConfigEntry) -> str:
    """Return the storage key for persistent heat producer identities."""
    return f"{DOMAIN}.{entry.entry_id}.producer_ids"


def legacy_producer_ids_storage_key(entry: ConfigEntry) -> str:
    """Return the key used by early versions of the collision fix."""
    return f"{DOMAIN}_producer_ids_{entry.entry_id}"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Remeha Home."""
    hass.data.setdefault(DOMAIN, {})

    RemehaHomeLoginFlowHandler.async_register_implementation(
        hass,
        RemehaHomeOAuth2Implementation(async_get_clientsession(hass)),
    )

    async_register_energy_history_service(hass)

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
    coordinator = RemehaHomeUpdateCoordinator(hass, api, entry)
    producer_store = Store(hass, 1, producer_ids_storage_key(entry))
    saved_producer_ids = await producer_store.async_load()
    if saved_producer_ids is None:
        # Don't discard assignments from an already-installed preview of this PR.
        legacy_store = Store(hass, 1, legacy_producer_ids_storage_key(entry))
        saved_producer_ids = await legacy_store.async_load()
        if saved_producer_ids is not None:
            producer_store.async_delay_save(lambda: dict(saved_producer_ids), 1)
    coordinator.producer_id_resolver = ProducerIdResolver(saved_producer_ids)

    @callback
    def save_producer_ids() -> None:
        """Persist assigned producer IDs without affecting climate updates."""
        producer_store.async_delay_save(
            lambda: dict(coordinator.producer_id_resolver.assignments), 1
        )

    coordinator.on_producer_ids_changed = save_producer_ids
    holiday_restorer = HolidayModeRestorer(hass, entry, coordinator, api)
    await holiday_restorer.async_load()

    await coordinator.async_config_entry_first_refresh()
    entry.async_on_unload(coordinator.async_add_listener(holiday_restorer.async_update))
    holiday_restorer.async_update()

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove stored holiday modes and producer IDs with the config entry."""
    await Store(hass, STORAGE_VERSION, storage_key(entry)).async_remove()
    await Store(hass, 1, producer_ids_storage_key(entry)).async_remove()
    await Store(hass, 1, legacy_producer_ids_storage_key(entry)).async_remove()
