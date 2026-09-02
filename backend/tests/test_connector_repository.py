import asyncio

import httpx
import pytest

from devstacks_api.repositories import (
    RepositoryUnavailableError,
    SupabaseConnectorRepository,
    SupabaseServiceSettings,
)
from devstacks_domain import TenantContext


CONNECTION_ROW = {
    "id": "connection-1",
    "platform": "github",
    "external_subject": "octocat",
    "connection_status": "active",
    "connected_at": "2026-08-26T00:00:00+00:00",
    "last_synced_at": "2026-08-27T00:00:00+00:00",
}

NEWER_RUN_ROW = {
    "id": "run-2",
    "connection_id": "connection-1",
    "status": "succeeded",
    "trigger_type": "manual",
    "created_at": "2026-08-27T00:00:00+00:00",
    "started_at": "2026-08-27T00:00:01+00:00",
    "completed_at": "2026-08-27T00:00:09+00:00",
    "error_summary": None,
}

OLDER_RUN_ROW = {
    "id": "run-1",
    "connection_id": "connection-1",
    "status": "failed",
    "trigger_type": "scheduled",
    "created_at": "2026-08-26T00:00:00+00:00",
    "started_at": "2026-08-26T00:00:01+00:00",
    "completed_at": "2026-08-26T00:00:04+00:00",
    "error_summary": "rate limited",
}


def _repository(handler) -> SupabaseConnectorRepository:
    return SupabaseConnectorRepository(
        SupabaseServiceSettings(
            url="https://project.supabase.co",
            service_role_key="server-only-key",
        ),
        transport=httpx.MockTransport(handler),
    )


def test_connector_repository_scopes_every_query_to_the_authenticated_tenant():
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        assert request.headers["apikey"] == "server-only-key"
        assert request.url.params["profile_id"] == "eq.profile-1"
        if request.url.path.endswith("/source_connections"):
            return httpx.Response(200, json=[CONNECTION_ROW])
        return httpx.Response(200, json=[NEWER_RUN_ROW, OLDER_RUN_ROW])

    connectors = asyncio.run(_repository(handler).list_own_connectors(TenantContext("profile-1")))

    assert seen_paths == ["/rest/v1/source_connections", "/rest/v1/ingestion_runs"]
    assert len(connectors) == 1
    assert connectors[0].id == "connection-1"
    assert connectors[0].platform == "github"
    assert connectors[0].external_subject == "octocat"


def test_connector_repository_never_selects_credential_columns():
    def handler(request: httpx.Request) -> httpx.Response:
        selected = request.url.params["select"]
        assert "token" not in selected
        assert "encrypted" not in selected
        if request.url.path.endswith("/source_connections"):
            return httpx.Response(200, json=[CONNECTION_ROW])
        return httpx.Response(200, json=[])

    asyncio.run(_repository(handler).list_own_connectors(TenantContext("profile-1")))


def test_connector_repository_attaches_only_the_newest_run_per_connection():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/source_connections"):
            return httpx.Response(200, json=[CONNECTION_ROW])
        assert request.url.params["order"] == "created_at.desc"
        return httpx.Response(200, json=[NEWER_RUN_ROW, OLDER_RUN_ROW])

    connectors = asyncio.run(_repository(handler).list_own_connectors(TenantContext("profile-1")))

    latest_run = connectors[0].latest_run
    assert latest_run is not None
    assert latest_run.id == "run-2"
    assert latest_run.status == "succeeded"


def test_connector_repository_returns_a_connection_without_runs():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/source_connections"):
            return httpx.Response(200, json=[CONNECTION_ROW])
        return httpx.Response(200, json=[])

    connectors = asyncio.run(_repository(handler).list_own_connectors(TenantContext("profile-1")))

    assert connectors[0].latest_run is None


def test_connector_repository_skips_the_run_query_without_connections():
    requested = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requested
        requested += 1
        return httpx.Response(200, json=[])

    connectors = asyncio.run(_repository(handler).list_own_connectors(TenantContext("profile-1")))

    assert connectors == ()
    assert requested == 1


def test_connector_repository_reads_one_run_scoped_to_its_owner():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["id"] == "eq.run-2"
        assert request.url.params["profile_id"] == "eq.profile-1"
        return httpx.Response(200, json=[NEWER_RUN_ROW])

    run = asyncio.run(_repository(handler).get_own_run(TenantContext("profile-1"), "run-2"))

    assert run is not None
    assert run.id == "run-2"
    assert run.completed_at == "2026-08-27T00:00:09+00:00"


def test_connector_repository_returns_none_for_another_tenants_run():
    run = asyncio.run(
        _repository(lambda request: httpx.Response(200, json=[])).get_own_run(
            TenantContext("profile-1"), "run-2"
        )
    )

    assert run is None


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={"message": "boom"}),
        httpx.Response(200, json={"unexpected": "shape"}),
        httpx.Response(200, json=["not-a-record"]),
    ],
)
def test_connector_repository_rejects_unusable_responses(response: httpx.Response):
    repository = _repository(lambda request: response)

    with pytest.raises(RepositoryUnavailableError):
        asyncio.run(repository.list_own_connectors(TenantContext("profile-1")))


def test_connector_repository_rejects_an_incomplete_run_record():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/source_connections"):
            return httpx.Response(200, json=[CONNECTION_ROW])
        return httpx.Response(200, json=[{"connection_id": "connection-1", "status": "queued"}])

    with pytest.raises(RepositoryUnavailableError):
        asyncio.run(_repository(handler).list_own_connectors(TenantContext("profile-1")))


def test_connector_repository_rejects_an_incomplete_connection_record():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/source_connections"):
            return httpx.Response(200, json=[{"id": "connection-1"}])
        return httpx.Response(200, json=[])

    with pytest.raises(RepositoryUnavailableError):
        asyncio.run(_repository(handler).list_own_connectors(TenantContext("profile-1")))


def test_connector_repository_reports_transport_failure_as_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(RepositoryUnavailableError):
        asyncio.run(_repository(handler).list_own_connectors(TenantContext("profile-1")))
