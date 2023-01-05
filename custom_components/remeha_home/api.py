"""API for Remeha Home bound to Home Assistant OAuth."""
import logging

import async_timeout
from aiohttp import ClientSession

from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
    OAuth2Session,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class RemehaHomeAPI:
    """Provide Remeha Home authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        oauth_session: OAuth2Session = None,
    ) -> None:
        """Initialize Remeha Home auth."""
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        _LOGGER.warning("GOT HERE")
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token["access_token"]

    async def _async_api_request(self, method: str, path: str, **kwargs):
        headers = kwargs.pop("headers", {})
        return await self._oauth_session.async_request(
            method,
            "https://api.bdrthermea.net/Mobile/api" + path,
            **kwargs,
            headers={
                **headers,
                "Ocp-Apim-Subscription-Key": "df605c5470d846fc91e848b1cc653ddf",
            },
        )

    async def async_get_dashboard(self) -> dict:
        """Return the Remeha Home dashboard JSON."""
        response = await self._async_api_request("GET", "/homes/dashboard")
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
        """Set a climate zone to schedule mode with a specific heating program."""
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


class RemehaHomeOAuth2Implementation(AbstractOAuth2Implementation):
    """Custom OAuth2 implementation for the Remeha Home integration."""

    def __init__(self, session: ClientSession) -> None:
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
        grant_params = {
            "grant_type": "refresh_token",
            "refresh_token": external_data["token"],
        }
        token = await self._async_request_new_token(grant_params)

        if not token:
            _LOGGER.error("Could not get token")
            raise Exception("Could not get token")

        return token

    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh a token."""
        grant_params = {
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
        }
        new_token = await self._async_request_new_token(grant_params)

        if not new_token:
            raise Exception("Could not get new token")

        return new_token

    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Generate a url for the user to authorize."""
        return ""

    async def _async_request_new_token(self, grant_params):
        """Call the OAuth2 token endpoint with specific grant paramters."""
        with async_timeout.timeout(30):
            async with self._session.post(
                "https://remehalogin.bdrthermea.net/bdrb2cprod.onmicrosoft.com/oauth2/v2.0/token?p=B2C_1A_RPSignUpSignInNewRoomV3.1",
                data=grant_params,
                allow_redirects=True,
            ) as response:
                response.raise_for_status()
                response_json = await response.json()

        return response_json
