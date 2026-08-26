from base64 import urlsafe_b64encode
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from os import getenv
from secrets import token_urlsafe
from typing import Protocol
from urllib.parse import urlencode, urlparse

import httpx

from devstacks_domain import FernetTokenCipher, TenantContext, TokenCipherError


class GitHubOAuthError(ValueError):
    """Raised when a GitHub OAuth authorization cannot be completed safely."""


class GitHubOAuthUnavailableError(RuntimeError):
    """Raised when GitHub OAuth configuration or transport is unavailable."""


@dataclass(frozen=True)
class GitHubOAuthSettings:
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: tuple[str, ...] = ("read:user",)

    @classmethod
    def from_environment(cls) -> "GitHubOAuthSettings":
        client_id = getenv("GITHUB_OAUTH_CLIENT_ID", "")
        client_secret = getenv("GITHUB_OAUTH_CLIENT_SECRET", "")
        redirect_uri = getenv("GITHUB_OAUTH_REDIRECT_URI", "")
        scopes = tuple(scope for scope in getenv("GITHUB_OAUTH_SCOPES", "read:user").split() if scope)
        if not client_id or not client_secret or not redirect_uri or not scopes:
            raise GitHubOAuthUnavailableError("GitHub OAuth is not configured")
        parsed_uri = urlparse(redirect_uri)
        if parsed_uri.scheme != "https" and not (
            parsed_uri.scheme == "http" and parsed_uri.hostname in {"127.0.0.1", "::1"}
        ):
            raise GitHubOAuthUnavailableError("GitHub OAuth callback URL is invalid")
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scopes=scopes,
        )


@dataclass(frozen=True)
class GitHubOAuthAttempt:
    profile_id: str
    code_verifier_encrypted: str
    redirect_uri: str


@dataclass(frozen=True)
class GitHubTokenExchange:
    access_token: str
    refresh_token: str | None
    access_token_expires_in: int | None
    refresh_token_expires_in: int | None
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class GitHubIdentity:
    subject_id: str
    login: str


@dataclass(frozen=True)
class GitHubConnection:
    id: str
    source_subject_id: str
    login: str


class GitHubAuthorizationRepository(Protocol):
    async def create_attempt(
        self,
        tenant: TenantContext,
        state_hash: str,
        code_verifier_encrypted: str,
        redirect_uri: str,
        expires_at: datetime,
    ) -> None:
        """Persist a server-only, single-use authorization attempt."""

    async def consume_attempt(self, state_hash: str) -> GitHubOAuthAttempt | None:
        """Atomically consume a current OAuth state hash."""

    async def complete_authorization(
        self,
        attempt: GitHubOAuthAttempt,
        identity: GitHubIdentity,
        token_exchange: GitHubTokenExchange,
        access_token_encrypted: str,
        refresh_token_encrypted: str | None,
        access_token_expires_at: datetime | None,
        refresh_token_expires_at: datetime | None,
    ) -> GitHubConnection:
        """Persist the validated identity and encrypted tokens for an attempt profile."""


class GitHubOAuthClient(Protocol):
    async def exchange_code(
        self,
        code: str,
        code_verifier: str,
    ) -> GitHubTokenExchange:
        """Exchange an authorization code using the original PKCE verifier."""

    async def get_identity(self, access_token: str) -> GitHubIdentity:
        """Return the identity currently authenticated by the access token."""


class GitHubOAuthService:
    def __init__(
        self,
        settings: GitHubOAuthSettings,
        cipher: FernetTokenCipher,
        repository: GitHubAuthorizationRepository,
        client: GitHubOAuthClient,
    ) -> None:
        self._settings = settings
        self._cipher = cipher
        self._repository = repository
        self._client = client

    async def begin(self, tenant: TenantContext) -> str:
        state = token_urlsafe(32)
        code_verifier = token_urlsafe(64)
        await self._repository.create_attempt(
            tenant=tenant,
            state_hash=self._hash(state),
            code_verifier_encrypted=self._cipher.encrypt(code_verifier),
            redirect_uri=self._settings.redirect_uri,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        code_challenge = urlsafe_b64encode(sha256(code_verifier.encode("ascii")).digest())
        parameters = {
            "client_id": self._settings.client_id,
            "redirect_uri": self._settings.redirect_uri,
            "scope": " ".join(self._settings.scopes),
            "state": state,
            "code_challenge": code_challenge.decode("ascii").rstrip("="),
            "code_challenge_method": "S256",
        }
        return f"https://github.com/login/oauth/authorize?{urlencode(parameters)}"

    async def complete(self, state: str, code: str) -> GitHubConnection:
        if not state or not code:
            raise GitHubOAuthError("GitHub OAuth callback is incomplete")
        attempt = await self._repository.consume_attempt(self._hash(state))
        if attempt is None:
            raise GitHubOAuthError("GitHub OAuth state is invalid, expired, or already used")
        try:
            code_verifier = self._cipher.decrypt(attempt.code_verifier_encrypted)
        except TokenCipherError as error:
            raise GitHubOAuthUnavailableError("GitHub OAuth state cannot be decrypted") from error
        token_exchange = await self._client.exchange_code(code, code_verifier)
        identity = await self._client.get_identity(token_exchange.access_token)
        now = datetime.now(timezone.utc)
        return await self._repository.complete_authorization(
            attempt=attempt,
            identity=identity,
            token_exchange=token_exchange,
            access_token_encrypted=self._cipher.encrypt(token_exchange.access_token),
            refresh_token_encrypted=(
                self._cipher.encrypt(token_exchange.refresh_token)
                if token_exchange.refresh_token
                else None
            ),
            access_token_expires_at=self._expires_at(now, token_exchange.access_token_expires_in),
            refresh_token_expires_at=self._expires_at(
                now,
                token_exchange.refresh_token_expires_in,
            ),
        )

    @staticmethod
    def _hash(value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _expires_at(now: datetime, expires_in: int | None) -> datetime | None:
        if expires_in is None:
            return None
        if expires_in <= 0:
            raise GitHubOAuthError("GitHub OAuth token expiry is invalid")
        return now + timedelta(seconds=expires_in)


class HttpGitHubOAuthClient:
    """Minimal GitHub OAuth App client using the authorization-code web flow."""

    def __init__(
        self,
        settings: GitHubOAuthSettings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def exchange_code(self, code: str, code_verifier: str) -> GitHubTokenExchange:
        try:
            async with httpx.AsyncClient(timeout=10.0, transport=self._transport) as client:
                response = await client.post(
                    "https://github.com/login/oauth/access_token",
                    data={
                        "client_id": self._settings.client_id,
                        "client_secret": self._settings.client_secret,
                        "code": code,
                        "redirect_uri": self._settings.redirect_uri,
                        "code_verifier": code_verifier,
                    },
                    headers={"Accept": "application/json"},
                )
        except httpx.HTTPError as error:
            raise GitHubOAuthUnavailableError("GitHub token exchange failed") from error
        if response.is_error:
            raise GitHubOAuthError("GitHub rejected the authorization code")
        try:
            payload = response.json()
        except ValueError as error:
            raise GitHubOAuthUnavailableError("GitHub token response is invalid") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("access_token"), str):
            raise GitHubOAuthError("GitHub token response is incomplete")
        scopes = payload.get("scope", "")
        if not isinstance(scopes, str):
            raise GitHubOAuthError("GitHub token scope is invalid")
        return GitHubTokenExchange(
            access_token=payload["access_token"],
            refresh_token=self._optional_string(payload, "refresh_token"),
            access_token_expires_in=self._optional_positive_int(payload, "expires_in"),
            refresh_token_expires_in=self._optional_positive_int(
                payload,
                "refresh_token_expires_in",
            ),
            scopes=tuple(scope for scope in scopes.split(",") if scope),
        )

    async def get_identity(self, access_token: str) -> GitHubIdentity:
        try:
            async with httpx.AsyncClient(timeout=10.0, transport=self._transport) as client:
                response = await client.get(
                    "https://api.github.com/user",
                    headers={
                        "Accept": "application/vnd.github+json",
                        "Authorization": f"Bearer {access_token}",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                )
        except httpx.HTTPError as error:
            raise GitHubOAuthUnavailableError("GitHub identity lookup failed") from error
        if response.is_error:
            raise GitHubOAuthError("GitHub identity lookup was rejected")
        try:
            payload = response.json()
        except ValueError as error:
            raise GitHubOAuthUnavailableError("GitHub identity response is invalid") from error
        subject_id = payload.get("id") if isinstance(payload, dict) else None
        login = payload.get("login") if isinstance(payload, dict) else None
        if not isinstance(subject_id, int) or not isinstance(login, str) or not login:
            raise GitHubOAuthError("GitHub identity response is incomplete")
        return GitHubIdentity(subject_id=str(subject_id), login=login)

    @staticmethod
    def _optional_string(payload: dict[str, object], name: str) -> str | None:
        value = payload.get(name)
        if value is None:
            return None
        if not isinstance(value, str) or not value:
            raise GitHubOAuthError(f"GitHub token {name} is invalid")
        return value

    @staticmethod
    def _optional_positive_int(payload: dict[str, object], name: str) -> int | None:
        value = payload.get(name)
        if value is None:
            return None
        if not isinstance(value, int) or value <= 0:
            raise GitHubOAuthError(f"GitHub token {name} is invalid")
        return value