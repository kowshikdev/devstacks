import asyncio
import json
from uuid import uuid4

import httpx
import pytest

from devstacks_api.repositories import (
    ProviderEventDraft,
    RepositoryUnavailableError,
    SupabaseProviderEventRepository,
    SupabaseServiceSettings,
)
from devstacks_domain import TenantContext


PROFILE_ID = str(uuid4())
CONNECTION_ID = str(uuid4())
EVENT_ID = str(uuid4())


def draft() -> ProviderEventDraft:
    return ProviderEventDraft(
        connection_id=CONNECTION_ID,
        provider_event_id="delivery-1",
        event_type="push",
        payload={"ref": "refs/heads/main"},
    )


def repository(handler):
    return SupabaseProviderEventRepository(
        SupabaseServiceSettings(
            url="https://project.supabase.co",
            service_role_key="server-only-key",
        ),
        transport=httpx.MockTransport(handler),
    )


def response_json() -> dict[str, str]:
    return {
        "id": EVENT_ID,
        "profile_id": PROFILE_ID,
        "connection_id": CONNECTION_ID,
        "provider_event_id": "delivery-1",
    }


def test_provider_event_repository_derives_profile_from_tenant():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/record_provider_event"
        assert request.headers["apikey"] == "server-only-key"
        assert request.headers.get("authorization") is None
        body = json.loads(request.content)
        assert body["p_profile_id"] == PROFILE_ID
        assert body["p_connection_id"] == CONNECTION_ID
        assert body["p_provider_event_id"] == "delivery-1"
        return httpx.Response(200, json=response_json())

    result = asyncio.run(repository(handler).record(TenantContext(PROFILE_ID), draft()))

    assert result.id == EVENT_ID
    assert result.profile_id == PROFILE_ID


@pytest.mark.parametrize(
    "kwargs",
    [
        {"connection_id": "invalid", "provider_event_id": "delivery", "event_type": "push"},
        {"connection_id": CONNECTION_ID, "provider_event_id": "", "event_type": "push"},
        {"connection_id": CONNECTION_ID, "provider_event_id": "delivery", "event_type": ""},
    ],
)
def test_provider_event_draft_rejects_invalid_inputs(kwargs):
    with pytest.raises(ValueError):
        ProviderEventDraft(payload={}, **kwargs)


def test_provider_event_repository_rejects_foreign_response():
    foreign = {**response_json(), "profile_id": str(uuid4())}

    with pytest.raises(RepositoryUnavailableError, match="tenant scope"):
        asyncio.run(
            repository(lambda request: httpx.Response(200, json=foreign)).record(
                TenantContext(PROFILE_ID),
                draft(),
            )
        )