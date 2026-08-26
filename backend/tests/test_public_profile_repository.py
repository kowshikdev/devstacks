import asyncio
import json

import httpx
import pytest

from devstacks_api.repositories import (
    RepositoryUnavailableError,
    SupabasePublicProfileRepository,
    SupabaseServiceSettings,
)


def repository(handler):
    return SupabasePublicProfileRepository(
        SupabaseServiceSettings(
            url="https://project.supabase.co",
            service_role_key="server-only-key",
        ),
        transport=httpx.MockTransport(handler),
    )


def published_claim() -> dict[str, str | None]:
    return {
        "profile_id": "profile-1",
        "handle": "devstacks",
        "display_name": "Dev Stacks",
        "claim_revision_id": "claim-revision-1",
        "category": "contribution",
        "statement": "Published claim only.",
        "assurance_class": "provider_observed",
        "freshness_status": "current",
        "last_verified_at": "2026-08-26T00:00:00+00:00",
    }


def test_public_profile_repository_calls_only_the_server_projection_rpc():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/get_published_profile"
        assert request.headers["apikey"] == "server-only-key"
        assert request.headers.get("authorization") == "Bearer server-only-key"
        assert json.loads(request.content) == {"p_handle": "devstacks"}
        return httpx.Response(200, json=[published_claim()])

    profile = asyncio.run(repository(handler).get_published_profile("devstacks"))

    assert profile is not None
    assert profile.handle == "devstacks"
    assert profile.claims[0].statement == "Published claim only."


def test_public_profile_repository_returns_none_when_projection_has_no_rows():
    profile = asyncio.run(
        repository(lambda request: httpx.Response(200, json=[])).get_published_profile(
            "devstacks"
        )
    )

    assert profile is None


def test_public_profile_repository_rejects_a_foreign_handle_in_the_response():
    foreign = {**published_claim(), "handle": "other-profile"}

    with pytest.raises(RepositoryUnavailableError, match="scope"):
        asyncio.run(
            repository(lambda request: httpx.Response(200, json=[foreign])).get_published_profile(
                "devstacks"
            )
        )