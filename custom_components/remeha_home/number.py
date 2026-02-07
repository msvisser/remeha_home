"""Platform for number integration."""

from __future__ import annotations
import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
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
    """Set up the Remeha Home number entities from a config entry."""
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = []
    for appliance in coordinator.data["appliances"]:
        for climate_zone in appliance["climateZones"]:
            climate_zone_id = climate_zone["climateZoneId"]

            activities = coordinator.get_activities(climate_zone_id)
            if activities is not None:
                for activity in activities:
                    if activity.get("type") == "Heating":
                        entities.append(
                            RemehaHomeActivityNumber(
                                api,
                                coordinator,
                                climate_zone_id,
                                activity["activityNumber"],
                                activity["name"],
                            )
                        )

    async_add_entities(entities)


class RemehaHomeActivityNumber(CoordinatorEntity, NumberEntity):
    """Representation of an activity temperature number entity."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        api: RemehaHomeAPI,
        coordinator: RemehaHomeUpdateCoordinator,
        climate_zone_id: str,
        activity_number: int,
        activity_name: str,
    ) -> None:
        """Create a Remeha Home activity temperature number entity."""
        super().__init__(coordinator)
        self.api = api
        self.climate_zone_id = climate_zone_id
        self.activity_number = activity_number

        key = f"activity_{activity_number}_temperature"
        self._attr_unique_id = "_".join([DOMAIN, self.climate_zone_id, key])
        self._attr_name = f"{activity_name} Temperature"

    @property
    def _activity(self) -> dict | None:
        """Return the activity data for this entity."""
        activities = self.coordinator.get_activities(self.climate_zone_id)
        if activities is None:
            return None
        return next(
            (a for a in activities if a["activityNumber"] == self.activity_number),
            None,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._activity is not None

    @property
    def native_value(self) -> float | None:
        """Return the current temperature value."""
        activity = self._activity
        if activity is None:
            return None
        return activity.get("temperature")

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        activity = self._activity
        if activity is None:
            return 5.0
        return activity.get("setPointMin", 5.0)

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        activity = self._activity
        if activity is None:
            return 30.0
        return activity.get("setPointMax", 30.0)

    @property
    def native_step(self) -> float:
        """Return the step value."""
        activity = self._activity
        if activity is None:
            return 0.5
        return activity.get("increment", 0.5)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_device_info(self.climate_zone_id)

    async def async_set_native_value(self, value: float) -> None:
        """Set the activity temperature value."""
        activities = self.coordinator.get_activities(self.climate_zone_id)
        if activities is None:
            return

        # Build the full activities payload with updated temperature
        payload = []
        for activity in activities:
            if activity.get("type") != "Heating":
                continue
            if activity["activityNumber"] == self.activity_number:
                temperature = value
            else:
                temperature = activity["temperature"]
            payload.append(
                {
                    "activityNumber": activity["activityNumber"],
                    "temperature": temperature,
                }
            )

        _LOGGER.debug(
            "Setting heating activities for zone %s: %s",
            self.climate_zone_id,
            payload,
        )
        await self.api.async_set_heating_activities(self.climate_zone_id, payload)

        # Invalidate cache to force re-fetch on next update
        self.coordinator.activities_data.pop(self.climate_zone_id, None)
        await self.coordinator.async_request_refresh()
