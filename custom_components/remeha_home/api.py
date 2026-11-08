"""API for Remeha Home bound to Home Assistant OAuth."""

from __future__ import annotations

import base64
from datetime import date, datetime, timedelta
import hashlib
import json
import logging
import secrets
import urllib.parse

import asyncio
from aiohttp import ClientSession, ClientTimeout

from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
    OAuth2Session,
)
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Home Assistant's shared session has no timeout of its own, so without one a request
# could hang for aiohttp's default of 5 minutes and hold up the updates.
REQUEST_TIMEOUT = 30

# Holiday mode: POST /appliances/{id}/holidayschedule (ApplianceHolidayScheduleRequestDto
# in the Remeha Home app), verified against the live API on 2026-10-22. The API keeps
# whole days only (it stores <date>T00:00:01Z) and updates the dashboard a few
# seconds after the request.
HOLIDAY_START_KEY = "holidayModeStartTime"
HOLIDAY_END_KEY = "holidayModeEndTime"
# Cancelling has no endpoint of its own: the app posts the "null" timestamps. The
# API requires start < end, so the start is one second before the empty value.
HOLIDAY_CANCEL_BODY = {
    HOLIDAY_START_KEY: "0001-01-01T00:00:00Z",
    HOLIDAY_END_KEY: "0001-01-01T00:00:01Z",
}


def _error_message(text: str) -> str:
    """Return the messages of a Remeha error response, or the start of the raw text.

    Remeha answers with problem details, e.g. {"title": "Bad Request",
    "errors": {"": ["Start Date must be before the End Date."]}}.
    """
    try:
        body = json.loads(text)
    except ValueError:
        return text[:500]
    if not isinstance(body, dict):
        return text[:500]

    errors = body.get("errors")
    messages = []
    if isinstance(errors, dict):
        for field_messages in errors.values():
            if isinstance(field_messages, list):
                messages.extend(str(message) for message in field_messages)
    return str(
        " ".join(messages) or body.get("detail") or body.get("title") or text[:500]
    )


class RemehaHomeAPI:
    """Provide Remeha Home authentication tied to an OAuth2 based config entry."""

    def __init__(self, oauth_session: OAuth2Session) -> None:
        """Initialize Remeha Home auth."""
        self._oauth_session = oauth_session

    async def _async_api_request(self, method: str, path: str, **kwargs):
        headers = kwargs.pop("headers", {})
        return await self._oauth_session.async_request(
            method,
            "https://api.bdrthermea.net/Mobile/api" + path,
            timeout=ClientTimeout(total=REQUEST_TIMEOUT),
            **kwargs,
            headers={
                **headers,
                "Ocp-Apim-Subscription-Key": "df605c5470d846fc91e848b1cc653ddf",
            },
        )

    async def async_get_dashboard(self) -> dict:
        """Return the Remeha Home dashboard JSON."""
        # Add a timestamp to the request to prevent caching
        timestamp = int(datetime.now().timestamp())
        response = await self._async_api_request(
            "GET", f"/homes/dashboard?t={timestamp}"
        )
        response.raise_for_status()
        return await response.json()

    async def async_set_manual(self, climate_zone_id: str, setpoint: float):
        """Set a climate zone to manual mode with a specific temperature setpoint."""
        response = await self._async_api_request(
            "POST",
            f"/climate-zones/{climate_zone_id}/modes/manual",
            json={
                "roomTemperatureSetPoint": setpoint,
            },
        )
        response.raise_for_status()

    async def async_set_schedule(self, climate_zone_id: str, heating_program_id: int):
        """Set a climate zone to schedule mode.

        The supplied heating program id should match the current heating program id.
        """
        response = await self._async_api_request(
            "POST",
            f"/climate-zones/{climate_zone_id}/modes/schedule",
            json={
                "heatingProgramId": heating_program_id,
            },
        )
        response.raise_for_status()

    async def async_set_temporary_override(self, climate_zone_id: str, setpoint: float):
        """Set a temporary temperature override for the current schedule in a climate zone."""
        response = await self._async_api_request(
            "POST",
            f"/climate-zones/{climate_zone_id}/modes/temporary-override",
            json={
                "roomTemperatureSetPoint": setpoint,
            },
        )
        response.raise_for_status()

    async def async_set_off(self, climate_zone_id: str):
        """Set a climate zone to off."""
        response = await self._async_api_request(
            "POST",
            f"/climate-zones/{climate_zone_id}/modes/anti-frost",
        )
        response.raise_for_status()

    async def async_activate_heating_time_program(
        self, climate_zone_id: str, time_program_id: int
    ):
        """Set a climate zone to schedule mode with a specific time program."""
        response = await self._async_api_request(
            "POST",
            f"/climate-zones/{climate_zone_id}/time-programs/heating/{time_program_id}/activate",
        )
        response.raise_for_status()

    async def async_set_fireplace_mode(self, climate_zone_id: str, enabled: bool):
        """Set fireplace mode for a climate zone."""
        response = await self._async_api_request(
            "POST",
            f"/climate-zones/{climate_zone_id}/modes/fireplacemode",
            json={"fireplaceModeActive": enabled},
        )
        response.raise_for_status()

    async def async_get_heating_curve(self, climate_zone_id: str) -> dict:
        """Get the heating curve parameters for a climate zone."""
        response = await self._async_api_request(
            "GET",
            f"/climate-zones/{climate_zone_id}/heating-curve",
        )
        response.raise_for_status()
        return await response.json()

    async def async_set_heating_curve(
        self, climate_zone_id: str, slope: float, base_setpoint: float
    ) -> None:
        """Set the heating curve for a climate zone."""
        response = await self._async_api_request(
            "POST",
            f"/climate-zones/{climate_zone_id}/heating-curve",
            json={"slope": slope, "baseSetpoint": base_setpoint},
        )
        response.raise_for_status()

    async def async_get_activities(self, climate_zone_id: str) -> list:
        """Get the activity definitions for a climate zone."""
        response = await self._async_api_request(
            "GET",
            f"/climate-zones/{climate_zone_id}/activities",
        )
        response.raise_for_status()
        return await response.json()

    async def async_set_heating_activities(
        self, climate_zone_id: str, activities: list[dict]
    ) -> None:
        """Set the heating activity temperatures for a climate zone."""
        response = await self._async_api_request(
            "PUT",
            f"/climate-zones/{climate_zone_id}/activities/heating",
            json=activities,
        )
        response.raise_for_status()

    async def _async_post_holiday_schedule(self, appliance_id: str, body: dict):
        """Post a holiday schedule, raising Remeha's own message when it is rejected."""
        response = await self._async_api_request(
            "POST", f"/appliances/{appliance_id}/holidayschedule", json=body
        )
        if response.status >= 400:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="holiday_request_rejected",
                translation_placeholders={
                    "status": str(response.status),
                    "message": _error_message(await response.text()),
                },
            )

    async def async_set_holiday_schedule(
        self, appliance_id: str, start_date: date, end_date: date
    ) -> None:
        """Schedule holiday mode for an appliance from start_date to end_date."""
        await self._async_post_holiday_schedule(
            appliance_id,
            {
                HOLIDAY_START_KEY: f"{start_date.isoformat()}T00:00:00Z",
                HOLIDAY_END_KEY: f"{end_date.isoformat()}T00:00:00Z",
            },
        )

    async def async_cancel_holiday_schedule(self, appliance_id: str) -> None:
        """Cancel an active or scheduled holiday mode."""
        await self._async_post_holiday_schedule(appliance_id, HOLIDAY_CANCEL_BODY)

    async def async_get_appliance_technical_information(
        self, appliance_id: str
    ) -> dict:
        """Get technical information for an appliance."""
        response = await self._async_api_request(
            "GET",
            f"/appliances/{appliance_id}/technicaldetails",
        )
        response.raise_for_status()
        return await response.json()

    async def async_get_consumption_data_for_today(self, appliance_id: str) -> dict:
        """Get technical information for an appliance."""
        today = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_of_today = today + timedelta(hours=23, minutes=59, seconds=59)

        today_string = today.strftime("%Y-%m-%d %H:%M:%S.%fZ")
        end_of_today_string = end_of_today.strftime("%Y-%m-%d %H:%M:%S.%fZ")

        response = await self._async_api_request(
            "GET",
            f"/appliances/{appliance_id}/energyconsumption/daily?startDate={today_string}&endDate={end_of_today_string}",
        )
        response.raise_for_status()
        return await response.json()

    async def async_get_consumption_data_for_range(
        self, appliance_id: str, start_date: date, end_date: date
    ) -> dict:
        """Get read-only daily energy history for an inclusive date range.

        The existing today poll is intentionally unchanged. Dates here are
        calendar dates, and both bounds are included in the API request.
        """
        start = f"{start_date.isoformat()}T00:00:00.000Z"
        end = f"{end_date.isoformat()}T23:59:59.999Z"
        response = await self._async_api_request(
            "GET",
            f"/appliances/{appliance_id}/energyconsumption/daily",
            params={"startDate": start, "endDate": end},
        )
        response.raise_for_status()
        return await response.json()

    async def async_set_dhw_comfort_setpoint(
        self, hot_water_zone_id: str, setpoint: float
    ):
        """Set the comfort (continuous) target temperature for a DHW zone."""
        response = await self._async_api_request(
            "POST",
            f"/hot-water-zones/{hot_water_zone_id}/comfort-setpoint",
            json={"comfortSetpoint": setpoint},
        )
        response.raise_for_status()

    async def async_set_dhw_reduced_setpoint(
        self, hot_water_zone_id: str, setpoint: float
    ):
        """Set the eco/reduced target temperature for a DHW zone."""
        response = await self._async_api_request(
            "POST",
            f"/hot-water-zones/{hot_water_zone_id}/reduced-setpoint",
            json={"reducedSetpoint": setpoint},
        )
        response.raise_for_status()

    async def async_set_dhw_mode_eco(self, hot_water_zone_id: str):
        """Switch the DHW zone to eco (anti-frost) mode."""
        response = await self._async_api_request(
            "POST",
            f"/hot-water-zones/{hot_water_zone_id}/modes/anti-frost",
        )
        response.raise_for_status()

    async def async_set_dhw_mode_schedule(self, hot_water_zone_id: str):
        """Switch the DHW zone to schedule mode."""
        response = await self._async_api_request(
            "POST",
            f"/hot-water-zones/{hot_water_zone_id}/modes/schedule",
        )
        response.raise_for_status()

    async def async_set_dhw_mode_comfort(self, hot_water_zone_id: str):
        """Switch the DHW zone to continuous comfort mode."""
        response = await self._async_api_request(
            "POST",
            f"/hot-water-zones/{hot_water_zone_id}/modes/continuous-comfort",
        )
        response.raise_for_status()

    async def async_set_hot_water_boost(self, hot_water_zone_id: str):
        """Activate boost mode for a DHW zone.

        Boost heats the water to the comfort setpoint for ~30 minutes. The API
        only accepts this from schedule mode and takes no request body, like the
        other DHW mode endpoints. Boost is cancelled by switching to another mode.
        """
        response = await self._async_api_request(
            "POST",
            f"/hot-water-zones/{hot_water_zone_id}/modes/boost",
        )
        response.raise_for_status()


class RemehaHomeAuthFailed(Exception):
    """Error to indicate that authentication failed."""


class RemehaHomeOAuth2Implementation(AbstractOAuth2Implementation):
    """Custom OAuth2 implementation for the Remeha Home integration."""

    def __init__(self, session: ClientSession) -> None:
        """Create a Remeha Home OAuth2 implementation."""
        self._session = session

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return "Remeha Home"

    @property
    def domain(self) -> str:
        """Domain that is providing the implementation."""
        return DOMAIN

    async def async_resolve_external_data(self, external_data) -> dict:
        """Resolve external data to tokens."""
        email = external_data["email"]
        password = external_data["password"]

        # Generate a random state and code challenge
        random_state = secrets.token_urlsafe()
        code_challenge = secrets.token_urlsafe(64)
        code_challenge_sha256 = (
            base64.urlsafe_b64encode(
                hashlib.sha256(code_challenge.encode("ascii")).digest()
            )
            .decode("ascii")
            .rstrip("=")
        )

        async with asyncio.timeout(60):
            # Request the login page starting a new login transaction
            response = await self._session.get(
                "https://remehalogin.bdrthermea.net/bdrb2cprod.onmicrosoft.com/oauth2/v2.0/authorize",
                params={
                    "response_type": "code",
                    "client_id": "6ce007c6-0628-419e-88f4-bee2e6418eec",
                    "redirect_uri": "com.b2c.remehaapp://login-callback",
                    "scope": "openid https://bdrb2cprod.onmicrosoft.com/iotdevice/user_impersonation offline_access",
                    "state": random_state,
                    "code_challenge": code_challenge_sha256,
                    "code_challenge_method": "S256",
                    "p": "B2C_1A_RPSignUpSignInNewRoomV3.1",
                    "brand": "remeha",
                    "lang": "en",
                    "nonce": "defaultNonce",
                    "prompt": "login",
                    "signUp": "False",
                },
            )
            response.raise_for_status()

            # Find the request id from the headers and package it up in base64 encoded json
            request_id = response.headers["x-request-id"]
            state_properties_json = f'{{"TID":"{request_id}"}}'.encode("ascii")
            state_properties = (
                base64.urlsafe_b64encode(state_properties_json)
                .decode("ascii")
                .rstrip("=")
            )

            # Find the CSRF token in the "x-ms-cpim-csrf" header
            csrf_token = next(
                cookie.value
                for cookie in self._session.cookie_jar
                if (
                    cookie.key == "x-ms-cpim-csrf"
                    and cookie["domain"] == "remehalogin.bdrthermea.net"
                )
            )

            # Post the user credentials to authenticate
            response = await self._session.post(
                "https://remehalogin.bdrthermea.net/bdrb2cprod.onmicrosoft.com/B2C_1A_RPSignUpSignInNewRoomv3.1/SelfAsserted",
                params={
                    "tx": "StateProperties=" + state_properties,
                    "p": "B2C_1A_RPSignUpSignInNewRoomv3.1",
                },
                headers={
                    "x-csrf-token": csrf_token,
                },
                data={
                    "request_type": "RESPONSE",
                    "signInName": email,
                    "password": password,
                },
            )
            response.raise_for_status()
            response_json = json.loads(await response.text())
            if response_json["status"] != "200":
                raise RemehaHomeAuthFailed

            # Request the authentication complete callback
            response = await self._session.get(
                "https://remehalogin.bdrthermea.net/bdrb2cprod.onmicrosoft.com/B2C_1A_RPSignUpSignInNewRoomv3.1/api/CombinedSigninAndSignup/confirmed",
                params={
                    "rememberMe": "false",
                    "csrf_token": csrf_token,
                    "tx": "StateProperties=" + state_properties,
                    "p": "B2C_1A_RPSignUpSignInNewRoomv3.1",
                },
                allow_redirects=False,
            )
            response.raise_for_status()

            # Parse the callback url for the authorization code
            parsed_callback_url = urllib.parse.urlparse(response.headers["location"])
            query_string_dict = urllib.parse.parse_qs(parsed_callback_url.query)
            # parse_qs returns a list of values for each parameter
            authorization_code = query_string_dict["code"][0]

            # Request a new token with the authorization code
            grant_params = {
                "grant_type": "authorization_code",
                "code": authorization_code,
                "redirect_uri": "com.b2c.remehaapp://login-callback",
                "code_verifier": code_challenge,
                "client_id": "6ce007c6-0628-419e-88f4-bee2e6418eec",
            }
            return await self._async_request_new_token(grant_params)

    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh a token."""
        grant_params = {
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
            "client_id": "6ce007c6-0628-419e-88f4-bee2e6418eec",
        }
        return await self._async_request_new_token(grant_params)

    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Generate a url for the user to authorize."""
        return ""

    async def _async_request_new_token(self, grant_params):
        """Call the OAuth2 token endpoint with specific grant paramters."""
        async with asyncio.timeout(30), self._session.post(
            "https://remehalogin.bdrthermea.net/bdrb2cprod.onmicrosoft.com/oauth2/v2.0/token?p=B2C_1A_RPSignUpSignInNewRoomV3.1",
            data=grant_params,
            allow_redirects=True,
        ) as response:
            # NOTE: The OAuth2 token request sometimes returns a "400 Bad Request" response. The root cause of this
            #       problem has not been found, but this workaround allows you to reauthenticate at least. Otherwise
            #       Home Assitant would get stuck on refreshing the token forever.
            if response.status == 400:
                # Usually JSON with an error_description, but not always
                try:
                    response_json = await response.json(content_type=None)
                    description = response_json.get("error_description")
                except (ValueError, AttributeError):
                    description = None
                _LOGGER.error(
                    "OAuth2 token request returned '400 Bad Request': %s",
                    description or "no error description",
                )
                raise ConfigEntryAuthFailed

            response.raise_for_status()
            response_json = await response.json()

        return response_json
