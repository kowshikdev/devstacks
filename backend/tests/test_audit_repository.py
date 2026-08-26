import asyncio
import json
from uuid import uuid4

import httpx
import pytest

from devstacks_api.repositories import (
    AuditEventDraft,
    RepositoryUnavailableError,
    SupabaseAuditRepository,
    SupabaseServiceSettings,
)
from devstacks_domain import TenantContext


PROFILE_ID = str(uuid4())
ENTITY_ID = str(uuid4())
EVENT_ID = str(uuid4())


def draft() -> AuditEventDraft:
    return AuditEventDraft(
        event_type="evidence_version.created",
        entity_type="evidence_version",
        entity_id=ENTITY_ID,
        idempotency_key="evidence-version:artifact-1:hash-1",
        payload={"content_hash": "hash-1"},
    )


def repository(handler):
    return SupabaseAuditRepository(
        SupabaseServiceSettings(
            url="https://project.supabase.co",
            service_role_key="server-only-key",
        ),
        transport=httpx.MockTransport(handler),
    )


def record_json() -> list[dict[str, str]]:
    return [
        {
            "id": EVENT_ID,
            "profile_id": PROFILE_ID,
            "idempotency_key": draft().idempotency_key,
        }
    ]


def test_audit_repository_derives_profile_from_tenant_and_appends_event():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.headers["apikey"] == "server-only-key"
        body = json.loads(request.content)
        assert body["profile_id"] == PROFILE_ID
        assert body["idempotency_key"] == draft().idempotency_key
        assert "authorization" not in request.headers
        return httpx.Response(201, json=record_json())

    record = asyncio.run(repository(handler).record(TenantContext(PROFILE_ID), draft()))

    assert record.id == EVENT_ID
    assert record.profile_id == PROFILE_ID


def test_audit_repository_recovers_existing_event_after_idempotency_conflict():
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.method)
        if request.method == "POST":
            return httpx.Response(409, json={"code": "23505"})
        assert request.url.params["profile_id"] == f"eq.{PROFILE_ID}"
        assert request.url.params["idempotency_key"] == f"eq.{draft().idempotency_key}"
        return httpx.Response(200, json=record_json())

    record = asyncio.run(repository(handler).record(TenantContext(PROFILE_ID), draft()))

    assert requests == ["POST", "GET"]
    assert record.id == EVENT_ID


@pytest.mark.parametrize(
    "kwargs",
    [
        {"event_type": "", "entity_type": "evidence", "entity_id": ENTITY_ID, "idempotency_key": "key"},
        {"event_type": "event", "entity_type": "evidence", "entity_id": "not-a-uuid", "idempotency_key": "key"},
        {"event_type": "event", "entity_type": "evidence", "entity_id": ENTITY_ID, "idempotency_key": ""},
    ],
)
def test_audit_event_draft_rejects_invalid_write_inputs(kwargs):
    with pytest.raises(ValueError):
        AuditEventDraft(payload={}, **kwargs)


def test_audit_repository_rejects_malformed_response():
    with pytest.raises(RepositoryUnavailableError):
        asyncio.run(
            repository(lambda request: httpx.Response(201, json={"id": EVENT_ID})).record(
                TenantContext(PROFILE_ID),
                draft(),
            )
        )