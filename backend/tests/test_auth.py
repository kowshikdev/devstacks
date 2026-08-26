from fastapi.testclient import TestClient

from devstacks_api.auth import (
    AccessTokenVerifier,
    AuthenticatedUser,
    AuthenticationError,
    AuthenticationUnavailableError,
)
from devstacks_api.main import app


class FakeVerifier(AccessTokenVerifier):
    def __init__(self, result: AuthenticatedUser | Exception) -> None:
        self._result = result

    async def validate(self, access_token: str) -> AuthenticatedUser:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def test_authenticated_endpoint_requires_bearer_token():
    response = TestClient(app).get("/v1/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_authenticated_endpoint_returns_supabase_subject():
    app.state.access_token_verifier = FakeVerifier(
        AuthenticatedUser(id="user-1", email="developer@example.com")
    )
    try:
        response = TestClient(app).get(
            "/v1/me",
            headers={"Authorization": "Bearer user-access-token"},
        )
    finally:
        del app.state.access_token_verifier

    assert response.status_code == 200
    assert response.json() == {"id": "user-1", "email": "developer@example.com"}


def test_invalid_supabase_token_returns_unauthorized():
    app.state.access_token_verifier = FakeVerifier(
        AuthenticationError("expired")
    )
    try:
        response = TestClient(app).get(
            "/v1/me",
            headers={"Authorization": "Bearer expired-token"},
        )
    finally:
        del app.state.access_token_verifier

    assert response.status_code == 401


def test_auth_service_outage_returns_unavailable():
    app.state.access_token_verifier = FakeVerifier(
        AuthenticationUnavailableError("offline")
    )
    try:
        response = TestClient(app).get(
            "/v1/me",
            headers={"Authorization": "Bearer user-access-token"},
        )
    finally:
        del app.state.access_token_verifier

    assert response.status_code == 503