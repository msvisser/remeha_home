"""Config flow for Remeha Home."""

import base64
import binascii
import json
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import DOMAIN
from .api import RemehaHomeAuthFailed, RemehaHomeOAuth2Implementation

_LOGGER = logging.getLogger(__name__)


def _account_id(token: dict) -> str | None:
    """Return the id of the Remeha account the token belongs to, if it has one.

    The access token is a JWT; its subject is the id of the account.
    """
    try:
        payload = token["access_token"].split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (KeyError, IndexError, AttributeError, binascii.Error, ValueError):
        return None
    if not isinstance(claims, dict):
        return None
    return claims.get("sub")


class RemehaHomeLoginFlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle RemehaHome authentication."""

    DOMAIN = DOMAIN

    def __init__(self):
        """Create a Remeha Home login flow."""
        super().__init__()
        self.flow_impl: RemehaHomeOAuth2Implementation = None  # type: ignore

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    async def async_step_reauth(self, user_input=None):
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
                last_step=False,
            )
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        # Home Assistant supports one Remeha Home account
        await self.async_set_unique_id(DOMAIN)
        if self.source != config_entries.SOURCE_REAUTH:
            self._abort_if_unique_id_configured()

        # Create a new session with a cookie jar that does not quote cookies
        # This is necessary to avoid issues with the Remeha Home authentication flow
        cookie_jar = aiohttp.CookieJar(quote_cookie=False)

        self.async_register_implementation(
            self.hass,
            RemehaHomeOAuth2Implementation(
                async_create_clientsession(self.hass, cookie_jar=cookie_jar)
            ),
        )

        return await super().async_step_user(user_input)

    async def async_step_auth(self, user_input=None) -> dict[str, Any]:
        """Create an entry for auth."""
        errors = {}

        if user_input and CONF_EMAIL in user_input and CONF_PASSWORD in user_input:
            self.external_data = {
                "email": user_input[CONF_EMAIL],
                "password": user_input[CONF_PASSWORD],
            }
            try:
                return await self.async_step_creation()
            except RemehaHomeAuthFailed:
                errors["base"] = "failed_to_authenticate"

        if user_input is None or errors:
            return self.async_show_form(
                step_id="auth",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_EMAIL, default=""): str,
                        vol.Required(CONF_PASSWORD, default=""): str,
                    }
                ),
                last_step=False,
                errors=errors,
            )

        return self.async_abort(reason="failed_to_authenticate")

    async def async_oauth_create_entry(self, data: dict) -> dict:
        """Create an oauth config entry or update existing entry for reauth."""
        if self.source == config_entries.SOURCE_REAUTH:
            entry = self._get_reauth_entry()
            old_account = _account_id(entry.data.get("token", {}))
            new_account = _account_id(data["token"])
            if old_account and new_account and old_account != new_account:
                return self.async_abort(reason="wrong_account")
            return self.async_update_reload_and_abort(entry, data=data)

        return self.async_create_entry(title=self.external_data["email"], data=data)
