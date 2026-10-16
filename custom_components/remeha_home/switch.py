"""Platform for switch integration."""

from __future__ import annotations
import logging


from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import RemehaHomeAPI
from .const import DOMAIN
from .coordinator import RemehaHomeUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Remeha Home switch entities from a config entry."""
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = []
    for appliance in coordinator.data["appliances"]:
        for climate_zone in appliance["climateZones"]:
            climate_zone_id = climate_zone["climateZoneId"]

            entities.append(
                RemehaHomeFireplaceModeSwitch(api, coordinator, climate_zone_id)
            )

        for hot_water_zone in appliance["hotWaterZones"]:
            if hot_water_zone.get("capabilityBoostMode", True):
                entities.append(
                    RemehaHomeDhwBoostSwitch(
                        api, coordinator, hot_water_zone["hotWaterZoneId"]
                    )
                )

    async_add_entities(entities)


class RemehaHomeSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a switch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        api: RemehaHomeAPI,
        coordinator: RemehaHomeUpdateCoordinator,
        climate_zone_id: str,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Create a Remeha Home switch entity."""
        super().__init__(coordinator)
        self.api = api
        self.climate_zone_id = climate_zone_id
        self.entity_description = entity_description

        self._attr_unique_id = "_".join(
            [DOMAIN, self.climate_zone_id, entity_description.key]
        )

    @property
    def _data(self):
        """Return the climate zone data for this switch."""
        return self.coordinator.get_by_id(self.climate_zone_id)

    @property
    def is_on(self) -> bool:
        """Return the state of this switch."""
        return self._data[self.entity_description.key]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_device_info(self.climate_zone_id)


class RemehaHomeFireplaceModeSwitch(RemehaHomeSwitch):
    """Representation of a fireplace mode switch."""

    def __init__(
        self,
        api: RemehaHomeAPI,
        coordinator: RemehaHomeUpdateCoordinator,
        climate_zone_id: str,
    ) -> None:
        """Create a Remeha Home fireplace mode switch entity."""
        super().__init__(
            api,
            coordinator,
            climate_zone_id,
            SwitchEntityDescription(
                key="firePlaceModeActive",
                name="Fireplace Mode",
                device_class=SwitchDeviceClass.SWITCH,
            ),
        )

    @property
    def icon(self):
        """Return the icon for this switch."""
        if self.is_on:
            return "mdi:fireplace"
        return "mdi:fireplace-off"

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        _LOGGER.debug("Enable fireplace mode")
        await self.api.async_set_fireplace_mode(self.climate_zone_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        _LOGGER.debug("Disable fireplace mode")
        await self.api.async_set_fireplace_mode(self.climate_zone_id, False)
        await self.coordinator.async_request_refresh()


class RemehaHomeDhwBoostSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to start and stop boost of a hot water zone.

    Remeha only accepts boost from schedule mode. Stopping the boost switches the
    zone back to schedule mode.
    """

    _attr_has_entity_name = True
    _attr_name = "Boost"

    def __init__(
        self,
        api: RemehaHomeAPI,
        coordinator: RemehaHomeUpdateCoordinator,
        hot_water_zone_id: str,
    ) -> None:
        """Create a Remeha Home DHW boost switch entity."""
        super().__init__(coordinator)
        self.api = api
        self.hot_water_zone_id = hot_water_zone_id
        self._attr_unique_id = "_".join([DOMAIN, self.hot_water_zone_id, "boost"])

    @property
    def _data(self):
        """Return the hot water zone data for this switch."""
        return self.coordinator.get_by_id(self.hot_water_zone_id)

    @property
    def is_on(self) -> bool:
        """Return whether the hot water zone is boosting."""
        return self._data.get("dhwZoneMode") == "Boost"

    @property
    def icon(self):
        """Return the icon for this switch."""
        if self.is_on:
            return "mdi:water-boiler"
        return "mdi:water-boiler-off"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_device_info(self.hot_water_zone_id)

    async def async_turn_on(self, **kwargs):
        """Start boost."""
        mode = self._data.get("dhwZoneMode")
        if mode == "Boost":
            return
        if mode != "Scheduling":
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="boost_requires_schedule",
            )

        _LOGGER.debug("Start DHW boost")
        await self._async_set_mode("Boost", self.api.async_set_hot_water_boost)

    async def async_turn_off(self, **kwargs):
        """Stop boost by switching back to schedule mode."""
        if not self.is_on:
            return

        _LOGGER.debug("Stop DHW boost")
        await self._async_set_mode("Scheduling", self.api.async_set_dhw_mode_schedule)

    async def _async_set_mode(self, mode: str, api_call) -> None:
        """Set the zone mode, with a temporary override until the next poll."""
        zone_data = self._data
        previous_mode = zone_data.get("dhwZoneMode")
        zone_data["dhwZoneMode"] = mode
        self.async_write_ha_state()

        try:
            await api_call(self.hot_water_zone_id)
        except Exception:
            # Revert the temporary override, the zone did not change
            zone_data["dhwZoneMode"] = previous_mode
            self.async_write_ha_state()
            raise

        await self.coordinator.async_request_refresh()
