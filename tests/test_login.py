"""Test the login with the Remeha account and the token requests."""

from __future__ import annotations

from http.cookies import Morsel
import json
from unittest.mock import MagicMock

from aiohttp import ContentTypeError
from homeassistant.exceptions import ConfigEntryAuthFailed
import pytest

from custom_components.remeha_home.api import RemehaHomeOAuth2Implementation

TOKEN = {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600}


class FakeResponse:
    """A response of the Remeha login, like aiohttp returns it."""

    def __init__(
        self,
        status: int = 200,
        body: str = "",
        content_type: str = "application/json",
        headers: dict | None = None,
    ) -> None:
        """Create a response."""
        self.status = status
        self.body = body
        self.content_type = content_type
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        """Fail on an error status, like aiohttp."""
        if self.status >= 400:
            raise AssertionError(f"raise_for_status() on {self.status}")

    async def text(self) -> str:
        """Return the body."""
        return self.body

    async def json(self, content_type: str | None = "application/json"):
        """Return the parsed body; aiohttp checks the content type unless it's None."""
        if content_type is not None and content_type != self.content_type:
            raise ContentTypeError(MagicMock(), ())
        return json.loads(self.body)

    async def __aenter__(self):
        """Use the response as a context manager, like aiohttp."""
        return self

    async def __aexit__(self, *args) -> None:
        """Leave the context manager."""


class FakeSession:
    """A session that answers the requests of the login.

    The token request gets `token_response`.
    """

    def __init__(self, token_response: FakeResponse) -> None:
        """Create a session with the CSRF cookie of the login page."""
        csrf = Morsel()
        csrf.set("x-ms-cpim-csrf", "csrf", "csrf")
        csrf["domain"] = "remehalogin.bdrthermea.net"
        self.cookie_jar = [csrf]
        self.token_response = token_response
        self.token_data = None

    async def get(self, url: str, **kwargs) -> FakeResponse:
        """Answer the login page and the confirmation."""
        if url.endswith("/authorize"):
            return FakeResponse(headers={"x-request-id": "request"})
        # The confirmation redirects to the app with the authorization code
        return FakeResponse(
            status=302,
            headers={"location": "com.b2c.remehaapp://login-callback?state=s&code=abc"},
        )

    def post(self, url: str, **kwargs):
        """Answer the credentials and the token request."""
        if "/oauth2/v2.0/token" in url:
            # Used as "async with"
            self.token_data = kwargs["data"]
            return self.token_response
        return self._credentials_accepted()

    async def _credentials_accepted(self) -> FakeResponse:
        return FakeResponse(body='{"status": "200"}')


async def test_login_sends_the_authorization_code() -> None:
    """The token request gets the code from the callback, as a single value."""
    session = FakeSession(FakeResponse(body=json.dumps(TOKEN)))
    implementation = RemehaHomeOAuth2Implementation(session)

    token = await implementation.async_resolve_external_data(
        {"email": "user@example.com", "password": "password"}
    )

    assert token == TOKEN
    assert session.token_data["code"] == "abc"


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse(400, '{"error": "invalid_grant", "error_description": "expired"}'),
        FakeResponse(400, '{"error": "invalid_grant"}'),
        FakeResponse(400, "<html>Bad Request</html>", content_type="text/html"),
    ],
    ids=["description", "no description", "html"],
)
async def test_rejected_token_refresh_starts_a_reauth(response, caplog) -> None:
    """A 400 on the token request asks to log in again, whatever its body."""
    implementation = RemehaHomeOAuth2Implementation(FakeSession(response))

    with pytest.raises(ConfigEntryAuthFailed):
        await implementation._async_refresh_token({"refresh_token": "refresh"})

    assert "OAuth2 token request returned '400 Bad Request'" in caplog.text
