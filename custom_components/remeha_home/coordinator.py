"""Coordinator for fetching the Remeha Home data."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
import logging

from aiohttp.client_exceptions import ClientError, ClientResponseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.redact import async_redact_data
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import RemehaHomeAPI
from .const import DOMAIN, TO_REDACT
from .producer_ids import ProducerIdResolver, is_valid_producer
from .util import detect_dhw_setpoint_activity

_LOGGER = logging.getLogger(__name__)

MAX_FAILED_UPDATES = 3

PRODUCER_TYPE_NAMES = {
    "HeatPumpAirSource": "Heat Pump (Air Source)",
    "HeatPumpGroundSource": "Heat Pump (Ground Source)",
    "HeatPumpWaterSource": "Heat Pump (Water Source)",
    "GasBoiler": "Gas Boiler",
    "OilBoiler": "Oil Boiler",
    "ElectricBoiler": "Electric Boiler",
    "CHP": "CHP",
}

PRODUCER_STATS = [
    "energyConsumptionCH",
    "energyConsumptionDHW",
    "energyConsumptionCooling",
    "energyConsumptionTotal",
    "energyProductionCH",
    "energyProductionDHW",
    "energyProductionCooling",
    "energyProductionTotal",
]

APPLIANCE_CONSUMPTION_DEFAULT_DATA = {
    "heatingEnergyConsumed": 0.0,
    "hotWaterEnergyConsumed": 0.0,
    "coolingEnergyConsumed": 0.0,
    "heatingEnergyDelivered": 0.0,
    "hotWaterEnergyDelivered": 0.0,
    "coolingEnergyDelivered": 0.0,
}


def get_producers(consumption: dict) -> list[dict]:
    """Return the producers (heat sources) in the consumption data of an appliance."""
    producer_stats = consumption.get("producerPerformanceStatistics")
    return (producer_stats or {}).get("producers") or []


class RemehaHomeUpdateCoordinator(DataUpdateCoordinator):
    """Remeha Home update coordinator."""

    def __init__(
        self, hass: HomeAssistant, api: RemehaHomeAPI, config_entry: ConfigEntry
    ) -> None:
        """Initialize Remeha Home update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )
        self.api = api
        self.items = {}
        self.device_info = {}
        self.technical_info = {}
        self.appliance_consumption_data = {}
        self.appliance_last_consumption_data_update = {}
        # Date of the last non-empty consumption data, to tell an empty response
        # during the day apart from the start of a new day
        self.appliance_consumption_data_date: dict[str, date] = {}
        self.appliance_producer_ids: dict[str, set[str]] = {}
        self.producer_id_resolver = ProducerIdResolver()
        self.on_producer_ids_changed = None
        self.dhw_activity_cache = {}
        self.heating_curve_data: dict[str, dict] = {}
        self.heating_curve_last_update: dict[str, datetime] = {}
        self.heating_curve_unsupported: set[str] = set()
        self.activities_data: dict[str, list] = {}
        # Failed updates in a row, see _async_update_data
        self.failed_updates = 0

    async def _async_update_data(self):
        """Fetch the data, and keep the previous data when an update fails once.

        The Remeha API regularly times out for a minute or two. Keeping the
        previous data for a few updates stops the entities from becoming
        unavailable every time that happens.
        """
        try:
            data = await self._async_fetch_data()
        except ClientResponseError as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            if err.status == 401:
                raise ConfigEntryAuthFailed from err
            reason = f"{err.status}, {err.message}"
            error = err
        except TimeoutError as err:
            reason = "timeout"
            error = err
        except ClientError as err:
            reason = str(err) or type(err).__name__
            error = err
        else:
            self.failed_updates = 0
            return data

        self.failed_updates += 1
        if self.data is not None and self.failed_updates < MAX_FAILED_UPDATES:
            _LOGGER.debug(
                "Failed to update the data (%s), keeping the previous data", reason
            )
            return self.data
        raise UpdateFailed(f"Failed to update the data: {reason}") from error

    async def _async_fetch_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        data = await self.api.async_get_dashboard()
        _LOGGER.debug(
            "Requested dashboard information: %s", async_redact_data(data, TO_REDACT)
        )

        # Save the current time for appliance usage data updates
        now = datetime.now()

        for appliance in data["appliances"]:
            appliance_id = appliance["applianceId"]
            self.items[appliance_id] = appliance

            # Request appliance technical information the first time it is discovered
            if appliance_id not in self.technical_info:
                self.technical_info[appliance_id] = (
                    await self.api.async_get_appliance_technical_information(
                        appliance_id
                    )
                )
                _LOGGER.debug(
                    "Requested technical information for appliance %s: %s",
                    appliance_id,
                    async_redact_data(self.technical_info[appliance_id], TO_REDACT),
                )

            # Only update appliance usage data every 15 minutes
            if (appliance_id not in self.appliance_last_consumption_data_update) or (
                now - self.appliance_last_consumption_data_update[appliance_id]
                >= timedelta(minutes=14, seconds=45)
            ):
                try:
                    consumption_data = (
                        await self.api.async_get_consumption_data_for_today(
                            appliance_id
                        )
                    )
                    _LOGGER.debug(
                        "Requested consumption data for appliance %s: %s",
                        appliance_id,
                        async_redact_data(consumption_data, TO_REDACT),
                    )

                    if len(consumption_data["data"]) > 0:
                        consumption = self._process_consumption_data(
                            appliance, consumption_data["data"][0]
                        )
                        self.appliance_consumption_data_date[appliance_id] = now.date()
                    elif self.appliance_consumption_data_date.get(appliance_id) == now.date():
                        # Empty response during the day: keep today's values, a drop to 0
                        # would be seen as a reset and double count the day's consumption
                        _LOGGER.debug(
                            "No consumption data found for appliance %s, keeping today's values",
                            appliance_id,
                        )
                        consumption = self.appliance_consumption_data[appliance_id]
                    else:
                        # Normal right after midnight, before the API has data for today
                        _LOGGER.debug(
                            "No consumption data found for appliance %s", appliance_id
                        )
                        consumption = dict(APPLIANCE_CONSUMPTION_DEFAULT_DATA)

                    self.appliance_consumption_data[appliance_id] = consumption
                    self.appliance_last_consumption_data_update[appliance_id] = now
                except ClientResponseError as err:
                    _LOGGER.warning(
                        "Failed to request consumption data for appliance %s: %s",
                        appliance_id,
                        err,
                    )
                except Exception:
                    # Consumption data is optional, so a problem with it must never
                    # fail the whole update and make the climate entities unavailable.
                    # Keep the previous data and retry at the next consumption interval.
                    _LOGGER.exception(
                        "Failed to update consumption data for appliance %s",
                        appliance_id,
                    )
                    self.appliance_last_consumption_data_update[appliance_id] = now

            # Get the cached consumption data for the appliance or use default values
            if appliance_id in self.appliance_consumption_data:
                appliance["consumptionData"] = self.appliance_consumption_data[
                    appliance_id
                ]
            else:
                appliance["consumptionData"] = dict(APPLIANCE_CONSUMPTION_DEFAULT_DATA)

            self.device_info[appliance_id] = DeviceInfo(
                identifiers={(DOMAIN, appliance_id)},
                name=appliance["houseName"],
                manufacturer="Remeha",
                model=self.technical_info[appliance_id]["applianceName"],
            )
            # Register the appliance first: its zones and producers are linked to
            # it by its device id
            appliance_device_id = (
                dr.async_get(self.hass)
                .async_get_or_create(
                    config_entry_id=self.config_entry.entry_id,
                    **self.device_info[appliance_id],
                )
                .id
            )

            for climate_zone in appliance["climateZones"]:
                climate_zone_id = climate_zone["climateZoneId"]
                # This assumes that all climate zones for an appliance share the same gateway
                gateways = self.technical_info[appliance_id][
                    "internetConnectedGateways"
                ]

                if len(gateways) > 1:
                    _LOGGER.warning(
                        "Appliance %s has more than one gateway, using technical information from the first one",
                        appliance_id,
                    )

                if len(gateways) > 0:
                    gateway_info = gateways[0]
                else:
                    _LOGGER.warning(
                        "Appliance %s has no gateways, using unknown values",
                        appliance_id,
                    )
                    gateway_info = {
                        "name": "Unknown",
                        "hardwareVersion": "Unknown",
                        "softwareVersion": "Unknown",
                    }

                await self._async_update_heating_curve(climate_zone_id, now)
                climate_zone["heatingCurve"] = self.heating_curve_data.get(
                    climate_zone_id, {}
                )
                self.items[climate_zone_id] = climate_zone

                # Fetch activities data once (re-fetched after writes)
                if climate_zone_id not in self.activities_data:
                    try:
                        self.activities_data[climate_zone_id] = (
                            await self.api.async_get_activities(climate_zone_id)
                        )
                        _LOGGER.debug(
                            "Requested activities data for climate zone %s: %s",
                            climate_zone_id,
                            async_redact_data(
                                self.activities_data[climate_zone_id], TO_REDACT
                            ),
                        )
                    except (ClientError, TimeoutError) as err:
                        # Optional: requested again at the next update
                        _LOGGER.warning(
                            "Failed to request activities data for climate zone %s: %r",
                            climate_zone_id,
                            err,
                        )

                self.device_info[climate_zone_id] = DeviceInfo(
                    identifiers={(DOMAIN, climate_zone_id)},
                    name=climate_zone["name"],
                    manufacturer="Remeha",
                    model=gateway_info["name"],
                    hw_version=gateway_info["hardwareVersion"],
                    sw_version=gateway_info["softwareVersion"],
                    via_device_id=appliance_device_id,
                )

            for hot_water_zone in appliance["hotWaterZones"]:
                hot_water_zone_id = hot_water_zone["hotWaterZoneId"]
                hot_water_zone["dhwCurrentActivity"] = self._derive_dhw_activity(
                    hot_water_zone
                )

                self.items[hot_water_zone_id] = hot_water_zone
                self.device_info[hot_water_zone_id] = DeviceInfo(
                    identifiers={(DOMAIN, hot_water_zone_id)},
                    name=hot_water_zone["name"],
                    manufacturer="Remeha",
                    model="Hot Water Zone",
                    via_device_id=appliance_device_id,
                )

            self._update_producers(
                appliance_id,
                appliance_device_id,
                get_producers(appliance["consumptionData"]),
            )
        return data

    async def _async_update_heating_curve(
        self, climate_zone_id: str, now: datetime
    ) -> None:
        """Request the heating curve of a climate zone every 15 minutes."""
        if climate_zone_id in self.heating_curve_unsupported:
            return

        last_update = self.heating_curve_last_update.get(climate_zone_id)
        if last_update is not None and now - last_update < timedelta(
            minutes=14, seconds=45
        ):
            return

        self.heating_curve_last_update[climate_zone_id] = now
        try:
            self.heating_curve_data[climate_zone_id] = (
                await self.api.async_get_heating_curve(climate_zone_id)
            )
            _LOGGER.debug(
                "Requested heating curve data for climate zone %s: %s",
                climate_zone_id,
                self.heating_curve_data[climate_zone_id],
            )
        except ClientResponseError as err:
            # A client error before any successful request means the zone has no heating curve
            if (
                climate_zone_id not in self.heating_curve_data
                and 400 <= err.status < 500
            ):
                self.heating_curve_unsupported.add(climate_zone_id)
                _LOGGER.info(
                    "Heating curve is not available for climate zone %s: %s",
                    climate_zone_id,
                    err,
                )
            else:
                _LOGGER.warning(
                    "Failed to request heating curve data for climate zone %s: %s",
                    climate_zone_id,
                    err,
                )
        except (ClientError, TimeoutError) as err:
            # Optional: requested again at the next interval
            _LOGGER.warning(
                "Failed to request heating curve data for climate zone %s: %r",
                climate_zone_id,
                err,
            )

    def invalidate_heating_curve(self, climate_zone_id: str) -> None:
        """Request the heating curve of a climate zone again on the next update."""
        self.heating_curve_last_update.pop(climate_zone_id, None)

    def _update_producers(
        self, appliance_id: str, appliance_device_id: str, producers: list[dict]
    ) -> None:
        """Register the producers (heat sources) of an appliance as devices."""
        # A hybrid may initially report only its boiler. If an electric entity
        # already owns that instance's legacy ID, don't reassign it to gas.
        existing_electric_legacy_ids = set()
        if self.items[appliance_id].get("applianceType") == "HeatPump":
            entity_registry = er.async_get(self.hass)
            for producer in producers:
                if not is_valid_producer(producer):
                    continue
                if producer.get("energyType") != "NaturalGas":
                    continue
                legacy = f"{appliance_id}_{producer['instanceWithinDevice']}"
                if entity_registry.async_get_entity_id(
                    "sensor", DOMAIN, f"{DOMAIN}_{legacy}_seasonalEfficiency"
                ):
                    existing_electric_legacy_ids.add(legacy)

        resolved, changed = self.producer_id_resolver.resolve(
            appliance_id,
            producers,
            appliance_type=self.items[appliance_id].get("applianceType"),
            existing_electric_legacy_ids=existing_electric_legacy_ids,
        )
        type_counts = Counter(producer.get("producerType") for producer, _ in resolved)
        current_ids = set()

        for producer, producer_id in resolved:
            current_ids.add(producer_id)
            self.items[producer_id] = producer

            producer_type = producer.get("producerType", "Producer")
            producer_label = PRODUCER_TYPE_NAMES.get(producer_type, producer_type)
            # Only number the producers when there are several of the same type
            if type_counts[producer_type] > 1:
                name = f"{producer_label} {producer['instanceWithinDevice']}"
            else:
                name = producer_label
            self.device_info[producer_id] = DeviceInfo(
                identifiers={(DOMAIN, producer_id)},
                name=name,
                manufacturer="Remeha",
                model=producer_label,
                via_device_id=appliance_device_id,
            )

        # Right after midnight the API doesn't list the producers until the data
        # for the new day is reported. Their values for the new day are 0, not the
        # values of yesterday. The seasonal efficiency is kept, it's a running value.
        known_ids = self.appliance_producer_ids.setdefault(appliance_id, set())
        for producer_id in known_ids - current_ids:
            self.items[producer_id] = {
                **self.items[producer_id],
                **dict.fromkeys(PRODUCER_STATS, 0.0),
            }
        known_ids |= current_ids
        if changed and self.on_producer_ids_changed is not None:
            self.on_producer_ids_changed()

    def _process_consumption_data(self, appliance: dict, consumption: dict) -> dict:
        """Prepare the consumption data of an appliance and its producers."""
        # Start from the defaults so a missing appliance total is 0.0 instead of unknown
        consumption = {**APPLIANCE_CONSUMPTION_DEFAULT_DATA, **consumption}

        for producer in get_producers(consumption):
            # The API reports null for energy a producer doesn't use or deliver, e.g.
            # hot water for a heat pump when the boiler heats the water
            for producer_stat in PRODUCER_STATS:
                if not isinstance(producer.get(producer_stat), int | float):
                    producer[producer_stat] = 0.0

            if producer.get("energyType") == "NaturalGas":
                # Recalculate energy values back to gas values when Gas device
                calorific_value = float(appliance["gasCalorificValue"])
                for key in ("energyConsumptionCH", "energyConsumptionDHW"):
                    producer[key] = round(producer[key] / calorific_value, 2)

        return consumption

    def get_by_id(self, item_id: str):
        """Return item with the specified item id."""
        return self.items.get(item_id)

    def get_device_info(self, item_id: str):
        """Return device info for the item with the specified id."""
        return self.device_info.get(item_id)

    def get_heating_curve(self, climate_zone_id: str) -> dict | None:
        """Return heating curve data for the specified climate zone."""
        return self.heating_curve_data.get(climate_zone_id)

    def get_activities(self, climate_zone_id: str) -> list | None:
        """Return activities data for the specified climate zone."""
        return self.activities_data.get(climate_zone_id)

    def _derive_dhw_activity(self, zone: dict) -> str | None:
        """Derive a human-friendly DHW activity label."""
        mode = zone.get("dhwZoneMode")
        if mode in ("ContinuousComfort", "Boost"):
            activity = "Comfort"
            self.dhw_activity_cache[zone.get("hotWaterZoneId")] = activity
            return activity
        if mode == "Scheduling":
            activity = detect_dhw_setpoint_activity(
                zone.get("targetSetpoint"),
                zone.get("comfortSetPoint"),
                zone.get("reducedSetpoint"),
            )
            if activity is not None:
                self.dhw_activity_cache[zone.get("hotWaterZoneId")] = activity
                return activity
            return self.dhw_activity_cache.get(zone.get("hotWaterZoneId"))
        if mode == "Off":
            # Called Eco in the Remeha Home app, the reduced setpoint applies
            activity = "Eco"
            self.dhw_activity_cache[zone.get("hotWaterZoneId")] = activity
            return activity
        return None
