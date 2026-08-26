from fastapi.testclient import TestClient

from devstacks_api.auth import AuthenticatedUser, get_access_token_verifier
from devstacks_api.github_oauth import GitHubConnection
from devstacks_api.main import app
from devstacks_api.repositories import PublishedClaim, PublishedProfile, ProfileSummary
from devstacks_domain import TenantContext


class FakeVerifier:
    async def validate(self, access_token: str) -> AuthenticatedUser:
        return AuthenticatedUser(id="profile-1", email="developer@example.com")


class FakeProfileRepository:
    def __init__(self, profile: ProfileSummary | None) -> None:
        self._profile = profile
        self.created: list[tuple[str, str | None]] = []

    async def get_own_profile(self, tenant: TenantContext) -> ProfileSummary | None:
        assert tenant.profile_id == "profile-1"
        return self._profile

    async def create_own_profile(self, tenant, handle, display_name) -> ProfileSummary:
        assert tenant.profile_id == "profile-1"
        self.created.append((handle, display_name))
        return ProfileSummary(id="profile-1", handle=handle, display_name=display_name, is_public=False)


class FakePublicProfileRepository:
    def __init__(self, profile: PublishedProfile | None) -> None:
        self._profile = profile

    async def get_published_profile(self, handle: str) -> PublishedProfile | None:
        assert handle == "devstacks"
        return self._profile


class FakeGitHubOAuthService:
    async def begin(self, tenant: TenantContext) -> str:
        assert tenant.profile_id == "profile-1"
        return "https://github.com/login/oauth/authorize?state=opaque"

    async def complete(self, state: str, code: str) -> GitHubConnection:
        assert state == "returned-state"
        assert code == "returned-code"
        return GitHubConnection("connection-1", "subject-1", "octocat")


class FakeIngestionJobRepository:
    async def enqueue_github(
        self,
        profile_id: str,
        connection_id: str,
        idempotency_key: str,
    ) -> str:
        assert profile_id == "profile-1"
        assert connection_id == "connection-1"
        assert idempotency_key == "sync-request-1"
        return "run-1"


def test_profile_endpoint_returns_only_authenticated_profile():
    app.state.access_token_verifier = FakeVerifier()
    app.state.profile_repository = FakeProfileRepository(
        ProfileSummary(
            id="profile-1",
            handle="devstacks",
            display_name="Dev Stacks",
            is_public=False,
        )
    )
    try:
        response = TestClient(app).get(
            "/v1/profile",
            headers={"Authorization": "Bearer user-access-token"},
        )
    finally:
        del app.state.access_token_verifier
        del app.state.profile_repository

    assert response.status_code == 200
    assert response.json()["id"] == "profile-1"
    assert response.json()["handle"] == "devstacks"


def test_profile_endpoint_returns_not_found_without_a_profile():
    app.state.access_token_verifier = FakeVerifier()
    app.state.profile_repository = FakeProfileRepository(None)
    try:
        response = TestClient(app).get(
            "/v1/profile",
            headers={"Authorization": "Bearer user-access-token"},
        )
    finally:
        del app.state.access_token_verifier
        del app.state.profile_repository

    assert response.status_code == 404


def test_create_profile_endpoint_creates_the_authenticated_tenants_profile():
    app.state.access_token_verifier = FakeVerifier()
    repository = FakeProfileRepository(None)
    app.state.profile_repository = repository
    try:
        response = TestClient(app).post(
            "/v1/profile",
            headers={"Authorization": "Bearer user-access-token"},
            json={"handle": "devstacks", "display_name": "Dev Stacks"},
        )
    finally:
        del app.state.access_token_verifier
        del app.state.profile_repository

    assert response.status_code == 200
    assert response.json()["handle"] == "devstacks"
    assert repository.created == [("devstacks", "Dev Stacks")]


def test_public_profile_endpoint_requires_no_bearer_token_and_projects_published_claims():
    app.state.public_profile_repository = FakePublicProfileRepository(
        PublishedProfile(
            id="profile-1",
            handle="devstacks",
            display_name="Dev Stacks",
            claims=(
                PublishedClaim(
                    id="claim-revision-1",
                    category="contribution",
                    statement="Published claim only.",
                    assurance_class="provider_observed",
                    freshness_status="current",
                    last_verified_at="2026-08-26T00:00:00+00:00",
                ),
            ),
        )
    )
    try:
        response = TestClient(app).get("/v1/public/profiles/devstacks")
    finally:
        del app.state.public_profile_repository

    assert response.status_code == 200
    assert response.json()["claims"] == [
        {
            "id": "claim-revision-1",
            "category": "contribution",
            "statement": "Published claim only.",
            "assurance_class": "provider_observed",
            "freshness_status": "current",
            "last_verified_at": "2026-08-26T00:00:00+00:00",
        }
    ]


def test_public_profile_endpoint_returns_not_found_for_an_absent_projection():
    app.state.public_profile_repository = FakePublicProfileRepository(None)
    try:
        response = TestClient(app).get("/v1/public/profiles/devstacks")
    finally:
        del app.state.public_profile_repository

    assert response.status_code == 404


def test_github_authorization_start_requires_bearer_authentication():
    response = TestClient(app).post("/v1/connectors/github/authorize")

    assert response.status_code == 401


def test_github_authorization_routes_start_authenticated_flow_and_complete_callback():
    app.state.access_token_verifier = FakeVerifier()
    app.state.github_oauth_service = FakeGitHubOAuthService()
    try:
        start = TestClient(app).post(
            "/v1/connectors/github/authorize",
            headers={"Authorization": "Bearer user-access-token"},
        )
        callback = TestClient(app).get(
            "/v1/connectors/github/callback",
            params={"state": "returned-state", "code": "returned-code"},
        )
    finally:
        del app.state.access_token_verifier
        del app.state.github_oauth_service

    assert start.status_code == 200
    assert start.json()["authorization_url"].startswith("https://github.com/")
    assert callback.status_code == 200
    assert callback.json() == {
        "connection_id": "connection-1",
        "source_subject_id": "subject-1",
        "github_login": "octocat",
    }


def test_github_sync_queues_an_authenticated_idempotent_ingestion_run():
    app.state.access_token_verifier = FakeVerifier()
    app.state.ingestion_job_repository = FakeIngestionJobRepository()
    try:
        response = TestClient(app).post(
            "/v1/connectors/github/connection-1/sync",
            headers={
                "Authorization": "Bearer user-access-token",
                "Idempotency-Key": "sync-request-1",
            },
        )
    finally:
        del app.state.access_token_verifier
        del app.state.ingestion_job_repository

    assert response.status_code == 200
    assert response.json() == {"run_id": "run-1"}


def test_github_sync_requires_an_idempotency_key():
    app.state.access_token_verifier = FakeVerifier()
    try:
        response = TestClient(app).post(
            "/v1/connectors/github/connection-1/sync",
            headers={"Authorization": "Bearer user-access-token"},
        )
    finally:
        del app.state.access_token_verifier

    assert response.status_code == 400