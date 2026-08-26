import asyncio
import json

import httpx
import pytest

from devstacks_api.repositories import (
    RepositoryUnavailableError,
    SupabaseProfileRepository,
    SupabaseServiceSettings,
)
from devstacks_domain import TenantContext


def test_profile_repository_reads_only_the_authenticated_tenant():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["apikey"] == "server-only-key"
        assert "authorization" not in request.headers
        assert request.url.params["id"] == "eq.profile-1"
        assert request.url.params["select"] == "id,handle,display_name,is_public"
        return httpx.Response(
            200,
            json=[
                {
                    "id": "profile-1",
                    "handle": "devstacks",
                    "display_name": "Dev Stacks",
                    "is_public": False,
                }
            ],
        )

    repository = SupabaseProfileRepository(
        SupabaseServiceSettings(
            url="https://project.supabase.co",
            service_role_key="server-only-key",
        ),
        transport=httpx.MockTransport(handler),
    )

    profile = asyncio.run(repository.get_own_profile(TenantContext("profile-1")))

    assert profile is not None
    assert profile.id == "profile-1"
    assert profile.handle == "devstacks"


def test_profile_repository_returns_none_for_no_profile():
    repository = SupabaseProfileRepository(
        SupabaseServiceSettings(
            url="https://project.supabase.co",
            service_role_key="server-only-key",
        ),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[])),
    )

    assert asyncio.run(repository.get_own_profile(TenantContext("profile-1"))) is None


@pytest.mark.parametrize(
    "body",
    [
        [{"id": "profile-2", "handle": "foreign", "is_public": False}],
        [{"id": "profile-1", "handle": "incomplete", "is_public": "false"}],
        {"id": "profile-1"},
    ],
)
def test_profile_repository_rejects_invalid_or_foreign_responses(body):
    repository = SupabaseProfileRepository(
        SupabaseServiceSettings(
            url="https://project.supabase.co",
            service_role_key="server-only-key",
        ),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)),
    )

    with pytest.raises(RepositoryUnavailableError):
        asyncio.run(repository.get_own_profile(TenantContext("profile-1")))


def test_profile_repository_does_not_return_data_for_api_failure():
    repository = SupabaseProfileRepository(
        SupabaseServiceSettings(
            url="https://project.supabase.co",
            service_role_key="server-only-key",
        ),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(500, content=json.dumps({"message": "error"}))
        ),
    )

    with pytest.raises(RepositoryUnavailableError):
        asyncio.run(repository.get_own_profile(TenantContext("profile-1")))