from fastapi.testclient import TestClient

from devstacks_api.auth import AuthenticatedUser
from devstacks_api.github_webhook_service import (
    GitHubWebhookProcessingResult,
    GitHubWebhookSubscription,
)
from devstacks_api.main import app
from devstacks_domain import TenantContext


class FakeVerifier:
    async def validate(self, access_token: str) -> AuthenticatedUser:
        return AuthenticatedUser(id="profile-1", email="developer@example.com")


class FakeWebhookService:
    async def handle(self, payload, signature, delivery_id, event_type, hook_id):
        assert payload == b'{"repository":{"id":101}}'
        assert signature == "sha256=verified"
        assert (delivery_id, event_type, hook_id) == ("delivery-1", "push", "456")
        return GitHubWebhookProcessingResult("run-1", False)


class FakeWebhookRepository:
    async def register_subscription(self, tenant, connection_id, draft):
        assert tenant == TenantContext("profile-1")
        assert connection_id == "connection-1"
        assert draft.github_repository_id == 101
        assert draft.github_hook_id == 456
        return GitHubWebhookSubscription("subscription-1", "profile-1", connection_id, 101, 456)


def test_webhook_endpoint_accepts_a_verified_delivery_without_bearer_authentication():
    app.state.github_webhook_service = FakeWebhookService()
    try:
        response = TestClient(app).post(
            "/v1/webhooks/github",
            content=b'{"repository":{"id":101}}',
            headers={
                "X-Hub-Signature-256": "sha256=verified",
                "X-GitHub-Delivery": "delivery-1",
                "X-GitHub-Event": "push",
                "X-GitHub-Hook-ID": "456",
            },
        )
    finally:
        del app.state.github_webhook_service

    assert response.status_code == 202
    assert response.json() == {"accepted": True, "queued_run_id": "run-1", "duplicate": False}


def test_webhook_subscription_registration_is_tenant_authenticated():
    app.state.access_token_verifier = FakeVerifier()
    app.state.github_webhook_repository = FakeWebhookRepository()
    try:
        response = TestClient(app).post(
            "/v1/connectors/github/connection-1/webhooks",
            params={"github_repository_id": 101, "github_hook_id": 456},
            headers={"Authorization": "Bearer user-access-token"},
        )
    finally:
        del app.state.access_token_verifier
        del app.state.github_webhook_repository

    assert response.status_code == 200
    assert response.json()["github_hook_id"] == 456


def test_webhook_subscription_registration_requires_bearer_authentication():
    response = TestClient(app).post(
        "/v1/connectors/github/connection-1/webhooks",
        params={"github_repository_id": 101, "github_hook_id": 456},
    )

    assert response.status_code == 401