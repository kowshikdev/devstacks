from fastapi.testclient import TestClient

from devstacks_api.auth import AuthenticatedUser
from devstacks_api.main import app
from devstacks_api.repositories import (
    ConnectorRun,
    ConnectorSummary,
    RepositoryUnavailableError,
)
from devstacks_domain import TenantContext


class FakeVerifier:
    async def validate(self, access_token: str) -> AuthenticatedUser:
        return AuthenticatedUser(id="profile-1", email="developer@example.com")


RUN = ConnectorRun(
    id="run-2",
    status="succeeded",
    trigger_type="manual",
    created_at="2026-08-27T00:00:00+00:00",
    started_at="2026-08-27T00:00:01+00:00",
    completed_at="2026-08-27T00:00:09+00:00",
    error_summary=None,
)

CONNECTOR = ConnectorSummary(
    id="connection-1",
    platform="github",
    external_subject="octocat",
    connection_status="active",
    connected_at="2026-08-26T00:00:00+00:00",
    last_synced_at="2026-08-27T00:00:00+00:00",
    latest_run=RUN,
)


class FakeConnectorRepository:
    def __init__(
        self,
        connectors: tuple[ConnectorSummary, ...] = (),
        run: ConnectorRun | None = None,
        unavailable: bool = False,
    ) -> None:
        self._connectors = connectors
        self._run = run
        self._unavailable = unavailable
        self.requested_runs: list[str] = []

    async def list_own_connectors(self, tenant: TenantContext) -> tuple[ConnectorSummary, ...]:
        assert tenant.profile_id == "profile-1"
        if self._unavailable:
            raise RepositoryUnavailableError("Supabase connector query failed")
        return self._connectors

    async def get_own_run(self, tenant: TenantContext, run_id: str) -> ConnectorRun | None:
        assert tenant.profile_id == "profile-1"
        self.requested_runs.append(run_id)
        if self._unavailable:
            raise RepositoryUnavailableError("Supabase connector query failed")
        return self._run


def _client_with(repository: FakeConnectorRepository) -> TestClient:
    app.state.access_token_verifier = FakeVerifier()
    app.state.connector_repository = repository
    return TestClient(app)


def _teardown() -> None:
    del app.state.access_token_verifier
    del app.state.connector_repository


def test_connectors_endpoint_projects_the_callers_connections():
    repository = FakeConnectorRepository(connectors=(CONNECTOR,))
    try:
        response = _client_with(repository).get(
            "/v1/connectors",
            headers={"Authorization": "Bearer user-access-token"},
        )
    finally:
        _teardown()

    assert response.status_code == 200
    assert response.json() == {
        "connectors": [
            {
                "id": "connection-1",
                "platform": "github",
                "external_subject": "octocat",
                "connection_status": "active",
                "connected_at": "2026-08-26T00:00:00+00:00",
                "last_synced_at": "2026-08-27T00:00:00+00:00",
                "latest_run": {
                    "id": "run-2",
                    "status": "succeeded",
                    "trigger_type": "manual",
                    "created_at": "2026-08-27T00:00:00+00:00",
                    "started_at": "2026-08-27T00:00:01+00:00",
                    "completed_at": "2026-08-27T00:00:09+00:00",
                    "error_summary": None,
                },
            }
        ]
    }


def test_connectors_endpoint_never_returns_credential_material():
    repository = FakeConnectorRepository(connectors=(CONNECTOR,))
    try:
        response = _client_with(repository).get(
            "/v1/connectors",
            headers={"Authorization": "Bearer user-access-token"},
        )
    finally:
        _teardown()

    body = response.text.lower()
    assert "token" not in body
    assert "encrypted" not in body
    assert "secret" not in body


def test_connectors_endpoint_returns_an_empty_list_without_connections():
    repository = FakeConnectorRepository()
    try:
        response = _client_with(repository).get(
            "/v1/connectors",
            headers={"Authorization": "Bearer user-access-token"},
        )
    finally:
        _teardown()

    assert response.status_code == 200
    assert response.json() == {"connectors": []}


def test_connectors_endpoint_requires_a_bearer_token():
    repository = FakeConnectorRepository(connectors=(CONNECTOR,))
    try:
        response = _client_with(repository).get("/v1/connectors")
    finally:
        _teardown()

    assert response.status_code == 401


def test_connectors_endpoint_reports_repository_failure_as_unavailable():
    repository = FakeConnectorRepository(unavailable=True)
    try:
        response = _client_with(repository).get(
            "/v1/connectors",
            headers={"Authorization": "Bearer user-access-token"},
        )
    finally:
        _teardown()

    assert response.status_code == 503


def test_ingestion_run_endpoint_reports_progress_for_an_owned_run():
    repository = FakeConnectorRepository(run=RUN)
    try:
        response = _client_with(repository).get(
            "/v1/ingestion-runs/run-2",
            headers={"Authorization": "Bearer user-access-token"},
        )
    finally:
        _teardown()

    assert response.status_code == 200
    assert response.json()["id"] == "run-2"
    assert response.json()["status"] == "succeeded"
    assert repository.requested_runs == ["run-2"]


def test_ingestion_run_endpoint_returns_not_found_for_another_tenants_run():
    repository = FakeConnectorRepository(run=None)
    try:
        response = _client_with(repository).get(
            "/v1/ingestion-runs/run-2",
            headers={"Authorization": "Bearer user-access-token"},
        )
    finally:
        _teardown()

    assert response.status_code == 404


def test_ingestion_run_endpoint_requires_a_bearer_token():
    repository = FakeConnectorRepository(run=RUN)
    try:
        response = _client_with(repository).get("/v1/ingestion-runs/run-2")
    finally:
        _teardown()

    assert response.status_code == 401
