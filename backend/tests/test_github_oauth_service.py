import asyncio
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet

from devstacks_api.github_oauth import (
    GitHubConnection,
    GitHubIdentity,
    GitHubOAuthAttempt,
    GitHubOAuthError,
    GitHubOAuthService,
    GitHubOAuthSettings,
    GitHubTokenExchange,
)
from devstacks_domain import FernetTokenCipher, TenantContext


class FakeRepository:
    def __init__(self, attempt: GitHubOAuthAttempt | None = None) -> None:
        self.attempt = attempt
        self.created: dict[str, object] | None = None
        self.completed: dict[str, object] | None = None

    async def create_attempt(self, **kwargs) -> None:
        self.created = kwargs

    async def consume_attempt(self, state_hash: str) -> GitHubOAuthAttempt | None:
        self.consumed_state_hash = state_hash
        return self.attempt

    async def complete_authorization(self, **kwargs) -> GitHubConnection:
        self.completed = kwargs
        return GitHubConnection("connection-1", "subject-1", kwargs["identity"].login)


class FakeClient:
    def __init__(self) -> None:
        self.exchange_called = False
        self.identity_called = False

    async def exchange_code(self, code: str, code_verifier: str) -> GitHubTokenExchange:
        self.exchange_called = True
        assert code == "authorization-code"
        assert code_verifier == "original-verifier"
        return GitHubTokenExchange("raw-access", "raw-refresh", 3600, None, ("read:user",))

    async def get_identity(self, access_token: str) -> GitHubIdentity:
        self.identity_called = True
        assert access_token == "raw-access"
        return GitHubIdentity("123", "octocat")


def settings() -> GitHubOAuthSettings:
    return GitHubOAuthSettings(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="http://127.0.0.1:8000/v1/connectors/github/callback",
    )


def cipher() -> FernetTokenCipher:
    return FernetTokenCipher(Fernet.generate_key().decode("ascii"))


def test_begin_persists_hashed_state_and_generates_pkce_authorization_url():
    fake_repository = FakeRepository()
    token_cipher = cipher()
    service = GitHubOAuthService(settings(), token_cipher, fake_repository, FakeClient())

    authorization_url = asyncio.run(service.begin(TenantContext("profile-1")))

    query = parse_qs(urlparse(authorization_url).query)
    state = query["state"][0]
    assert urlparse(authorization_url).netloc == "github.com"
    assert query["code_challenge_method"] == ["S256"]
    assert fake_repository.created is not None
    assert fake_repository.created["state_hash"] == sha256(state.encode()).hexdigest()
    assert token_cipher.decrypt(fake_repository.created["code_verifier_encrypted"])
    assert isinstance(fake_repository.created["expires_at"], datetime)


def test_complete_consumes_state_validates_identity_and_encrypts_tokens():
    token_cipher = cipher()
    fake_repository = FakeRepository(
        GitHubOAuthAttempt(
            "profile-1",
            token_cipher.encrypt("original-verifier"),
            settings().redirect_uri,
        )
    )
    fake_client = FakeClient()
    service = GitHubOAuthService(settings(), token_cipher, fake_repository, fake_client)

    connection = asyncio.run(service.complete("returned-state", "authorization-code"))

    assert fake_repository.consumed_state_hash == sha256(b"returned-state").hexdigest()
    assert fake_client.exchange_called and fake_client.identity_called
    assert fake_repository.completed is not None
    assert token_cipher.decrypt(fake_repository.completed["access_token_encrypted"]) == "raw-access"
    assert token_cipher.decrypt(fake_repository.completed["refresh_token_encrypted"]) == "raw-refresh"
    assert connection.login == "octocat"


def test_complete_rejects_replayed_state_before_contacting_github():
    fake_client = FakeClient()
    service = GitHubOAuthService(settings(), cipher(), FakeRepository(), fake_client)

    with pytest.raises(GitHubOAuthError, match="state"):
        asyncio.run(service.complete("replayed-state", "authorization-code"))

    assert not fake_client.exchange_called
    assert not fake_client.identity_called