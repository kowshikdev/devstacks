import asyncio
from datetime import datetime, timedelta, timezone
import json

import httpx

from devstacks_api.github_oauth import GitHubIdentity, GitHubOAuthAttempt, GitHubTokenExchange
from devstacks_api.repositories import (
    SupabaseGitHubAuthorizationRepository,
    SupabaseServiceSettings,
)
from devstacks_domain import TenantContext


PROFILE_ID = "profile-1"


def repository(handler):
    return SupabaseGitHubAuthorizationRepository(
        SupabaseServiceSettings(
            url="https://project.supabase.co",
            service_role_key="server-only-key",
        ),
        transport=httpx.MockTransport(handler),
    )


def test_github_authorization_repository_creates_server_only_attempt():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/create_github_oauth_attempt"
        assert request.headers["apikey"] == "server-only-key"
        assert request.headers.get("authorization") is None
        assert json.loads(request.content)["p_profile_id"] == PROFILE_ID
        return httpx.Response(200, json={"profile_id": PROFILE_ID})

    asyncio.run(
        repository(handler).create_attempt(
            TenantContext(PROFILE_ID),
            "a" * 64,
            "encrypted-verifier",
            "http://127.0.0.1:8000/v1/connectors/github/callback",
            datetime.now(timezone.utc) + timedelta(minutes=10),
        )
    )


def test_github_authorization_repository_returns_no_attempt_for_consumed_state():
    attempt = asyncio.run(
        repository(lambda request: httpx.Response(200, json=[])).consume_attempt("a" * 64)
    )

    assert attempt is None


def test_github_authorization_repository_persists_only_encrypted_token_values():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"connection_id": "connection-1", "source_subject_id": "subject-1"},
        )

    connection = asyncio.run(
        repository(handler).complete_authorization(
            GitHubOAuthAttempt(PROFILE_ID, "encrypted-verifier", "https://example.com/callback"),
            GitHubIdentity("123", "octocat"),
            GitHubTokenExchange("raw-access", "raw-refresh", 3600, None, ("read:user",)),
            "encrypted-access",
            "encrypted-refresh",
            datetime.now(timezone.utc) + timedelta(hours=1),
            None,
        )
    )

    body = json.loads(requests[0].content)
    assert requests[0].url.path == "/rest/v1/rpc/complete_github_authorization"
    assert body["p_access_token_encrypted"] == "encrypted-access"
    assert body["p_refresh_token_encrypted"] == "encrypted-refresh"
    assert "raw-access" not in requests[0].content.decode("utf-8")
    assert connection.login == "octocat"