from dataclasses import dataclass
from os import getenv
from typing import Protocol

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from devstacks_domain import TenantContext


class AuthenticationError(ValueError):
    """Raised when Supabase cannot validate a caller access token."""


class AuthenticationUnavailableError(RuntimeError):
    """Raised when the API has no usable Supabase auth configuration."""


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str | None


class AccessTokenVerifier(Protocol):
    async def validate(self, access_token: str) -> AuthenticatedUser:
        """Return the authenticated user for a valid Supabase access token."""


@dataclass(frozen=True)
class SupabaseAuthSettings:
    url: str
    publishable_key: str

    @classmethod
    def from_environment(cls) -> "SupabaseAuthSettings":
        url = getenv("SUPABASE_URL", "").rstrip("/")
        publishable_key = getenv("SUPABASE_PUBLISHABLE_KEY", "")
        if not url or not publishable_key:
            raise AuthenticationUnavailableError(
                "Supabase authentication is not configured"
            )
        return cls(url=url, publishable_key=publishable_key)


class SupabaseAccessTokenVerifier:
    def __init__(self, settings: SupabaseAuthSettings) -> None:
        self._settings = settings

    async def validate(self, access_token: str) -> AuthenticatedUser:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self._settings.url}/auth/v1/user",
                    headers={
                        "apikey": self._settings.publishable_key,
                        "Authorization": f"Bearer {access_token}",
                    },
                )
        except httpx.HTTPError as error:
            raise AuthenticationUnavailableError(
                "Supabase authentication is unavailable"
            ) from error

        if response.status_code in {401, 403}:
            raise AuthenticationError("access token is invalid or expired")
        if response.is_error:
            raise AuthenticationUnavailableError(
                "Supabase authentication returned an unexpected response"
            )

        payload = response.json()
        user_id = payload.get("id")
        if not isinstance(user_id, str) or not user_id:
            raise AuthenticationError("access token did not resolve to a user")
        email = payload.get("email")
        return AuthenticatedUser(id=user_id, email=email if isinstance(email, str) else None)


def get_access_token_verifier() -> AccessTokenVerifier:
    return SupabaseAccessTokenVerifier(SupabaseAuthSettings.from_environment())


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer authentication is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        verifier = getattr(request.app.state, "access_token_verifier", None)
        if verifier is None:
            verifier = get_access_token_verifier()
        return await verifier.validate(credentials.credentials)
    except AuthenticationError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    except AuthenticationUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable",
        ) from error


async def get_tenant_context(
    user: AuthenticatedUser = Depends(get_current_user),
) -> TenantContext:
    """Map the validated Supabase subject to the only permitted profile tenant."""
    return TenantContext(profile_id=user.id)