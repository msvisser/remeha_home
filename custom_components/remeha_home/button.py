"""Platform for button integration."""

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Remeha Home button entities from a config entry."""
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = []
    for appliance in coordinator.data["appliances"]:
        for hot_water_zone in appliance.get("hotWaterZones", []):
            hot_water_zone_id = hot_water_zone["hotWaterZoneId"]
            entities.append(
                RemehaHomeDHWBoostButton(api, coordinator, hot_water_zone_id)
            )

    async_add_entities(entities)


class RemehaHomeDHWBoostButton(ButtonEntity):
    """Button to activate DHW boost."""

    _attr_has_entity_name = True
    _attr_name = "DHW Boost"
    _attr_icon = "mdi:water-boiler"

    def __init__(self, api, coordinator, hot_water_zone_id: str) -> None:
        """Create the DHW boost button."""
        self._api = api
        self._coordinator = coordinator
        self._hot_water_zone_id = hot_water_zone_id
        self._attr_unique_id = f"{DOMAIN}_{hot_water_zone_id}_dhw_boost"
        self._attr_device_info = coordinator.get_device_info(hot_water_zone_id)

    async def async_press(self) -> None:
        """Activate DHW boost."""
        await self._api.async_activate_dhw_boost(self._hot_water_zone_id)
