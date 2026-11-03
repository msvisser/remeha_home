"""Test the config flow: the login and the re-authentication."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.remeha_home.api import RemehaHomeAuthFailed
from custom_components.remeha_home.const import DOMAIN

EMAIL = "user@example.com"
LOGIN = {CONF_EMAIL: EMAIL, CONF_PASSWORD: "password"}

TRANSLATIONS = (
    Path(__file__).parent.parent / "custom_components" / "remeha_home" / "translations"
)


def access_token(account: str) -> str:
    """Return an unsigned JWT for the account, like the tokens of the Remeha login."""

    def part(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    return f"{part({'alg': 'none'})}.{part({'sub': account})}.signature"


def token(account: str) -> dict:
    """Return the token the Remeha login returns for the account."""
    return {
        "access_token": access_token(account),
        "refresh_token": f"refresh-{account}",
        "expires_in": 3600,
        "token_type": "Bearer",
    }


def abort_text(reason: str) -> str | None:
    """Return the English text for an abort reason."""
    english = json.loads((TRANSLATIONS / "en.json").read_text(encoding="utf-8"))
    return english["config"]["abort"].get(reason)


@pytest.fixture
def existing_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a configured entry of the account "account-1"."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=EMAIL,
        unique_id=DOMAIN,
        data={"auth_implementation": DOMAIN, "token": token("account-1")},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_setup():
    """Don't set up the integration after the flow."""
    with (
        patch(
            "custom_components.remeha_home.async_setup_entry", return_value=True
        ) as mock_setup,
        patch("custom_components.remeha_home.async_unload_entry", return_value=True),
    ):
        yield mock_setup


async def log_in(hass: HomeAssistant, result: dict, login_result) -> dict:
    """Pick the implementation and fill in the login form."""
    if result["step_id"] == "pick_implementation":
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"implementation": DOMAIN}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"

    resolve = AsyncMock()
    if isinstance(login_result, Exception):
        resolve.side_effect = login_result
    else:
        resolve.return_value = login_result
    with patch(
        "custom_components.remeha_home.config_flow.RemehaHomeOAuth2Implementation"
        ".async_resolve_external_data",
        resolve,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], LOGIN
        )
        await hass.async_block_till_done()
    return result


async def test_login_creates_the_entry(hass: HomeAssistant, mock_setup) -> None:
    """A new login creates an entry named after the e-mail address."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await log_in(hass, result, token("account-1"))

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == EMAIL
    assert result["result"].unique_id == DOMAIN
    assert result["data"]["token"]["refresh_token"] == "refresh-account-1"


async def test_wrong_password_shows_an_error(hass: HomeAssistant, mock_setup) -> None:
    """A failed login shows the form again with an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await log_in(hass, result, RemehaHomeAuthFailed())

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "failed_to_authenticate"}


async def test_second_login_doesnt_replace_the_account(
    hass: HomeAssistant, existing_entry, mock_setup
) -> None:
    """Adding the integration again stops before the login."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert abort_text("already_configured")
    assert existing_entry.data["token"]["refresh_token"] == "refresh-account-1"


async def test_reauth_updates_the_token(
    hass: HomeAssistant, existing_entry, mock_setup, caplog
) -> None:
    """Logging in again with the same account stores the new token."""
    new_token = token("account-1") | {"refresh_token": "new-refresh"}
    caplog.set_level(logging.DEBUG, logger="custom_components.remeha_home")

    result = await existing_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await log_in(hass, result, new_token)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert abort_text("reauth_successful")
    assert existing_entry.data["token"]["refresh_token"] == "new-refresh"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    # The debug log doesn't show the tokens
    assert "refresh-account-1" not in caplog.text
    assert access_token("account-1") not in caplog.text


async def test_reauth_with_another_account_is_refused(
    hass: HomeAssistant, existing_entry, mock_setup
) -> None:
    """Re-authentication must not switch the entry to another account."""
    result = await existing_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await log_in(hass, result, token("account-2"))

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert abort_text("wrong_account")
    assert existing_entry.data["token"]["refresh_token"] == "refresh-account-1"
