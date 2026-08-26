import asyncio
import json

import httpx
import pytest

from devstacks_api.github_webhook_service import (
    GitHubWebhookSubscriptionDraft,
)
from devstacks_api.github_webhooks import GitHubWebhookDelivery
from devstacks_api.repositories import (
    RepositoryUnavailableError,
    SupabaseGitHubWebhookRepository,
    SupabaseServiceSettings,
)
from devstacks_domain import TenantContext


def repository(handler):
    return SupabaseGitHubWebhookRepository(
        SupabaseServiceSettings(
            url="https://project.supabase.co",
            service_role_key="server-only-key",
        ),
        transport=httpx.MockTransport(handler),
    )


def delivery() -> GitHubWebhookDelivery:
    return GitHubWebhookDelivery("delivery-1", "push", 456, {"repository": {"id": 101}})


def test_webhook_repository_registers_subscription_from_authenticated_tenant():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/register_github_webhook_subscription"
        assert request.headers["apikey"] == "server-only-key"
        assert json.loads(request.content) == {
            "p_profile_id": "profile-1",
            "p_connection_id": "connection-1",
            "p_github_repository_id": 101,
            "p_github_hook_id": 456,
        }
        return httpx.Response(
            200,
            json={
                "id": "subscription-1",
                "profile_id": "profile-1",
                "connection_id": "connection-1",
                "github_repository_id": 101,
                "github_hook_id": 456,
            },
        )

    subscription = asyncio.run(
        repository(handler).register_subscription(
            TenantContext("profile-1"),
            "connection-1",
            GitHubWebhookSubscriptionDraft(101, 456),
        )
    )

    assert subscription.id == "subscription-1"


def test_webhook_repository_processes_trusted_delivery_through_atomic_rpc():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/process_github_webhook_delivery"
        assert json.loads(request.content)["p_provider_event_id"] == "delivery-1"
        return httpx.Response(
            200,
            json=[
                {
                    "profile_id": "profile-1",
                    "connection_id": "connection-1",
                    "ingestion_run_id": "run-1",
                    "is_duplicate": False,
                }
            ],
        )

    result = asyncio.run(
        repository(handler).process_delivery(delivery(), {"github_repository_id": 101})
    )

    assert result is not None
    assert result.ingestion_run_id == "run-1"
    assert not result.is_duplicate


def test_webhook_repository_rejects_delivery_without_resolved_scope():
    with pytest.raises(RepositoryUnavailableError, match="scope"):
        asyncio.run(
            repository(
                lambda request: httpx.Response(
                    200,
                    json=[{"ingestion_run_id": "run-1", "is_duplicate": False}],
                )
            ).process_delivery(delivery(), {})
        )