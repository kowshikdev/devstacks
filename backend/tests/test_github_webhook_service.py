import asyncio
import hashlib
import hmac

import pytest

from devstacks_api.github_webhook_service import (
    GitHubWebhookProcessingResult,
    GitHubWebhookService,
)
from devstacks_api.github_webhooks import GitHubWebhookError, GitHubWebhookSettings


class FakeRepository:
    async def process_delivery(self, delivery, payload):
        self.delivery = delivery
        self.payload = payload
        return GitHubWebhookProcessingResult("run-1", False)


def signature(payload: bytes) -> str:
    return "sha256=" + hmac.new(b"secret", payload, hashlib.sha256).hexdigest()


def test_webhook_service_verifies_before_minimizing_and_processing_delivery():
    repository = FakeRepository()
    service = GitHubWebhookService(GitHubWebhookSettings("secret"), repository)
    raw_payload = b'{"action":"created","repository":{"id":101},"private":"not-stored"}'

    result = asyncio.run(
        service.handle(raw_payload, signature(raw_payload), "delivery-1", "push", "456")
    )

    assert result == GitHubWebhookProcessingResult("run-1", False)
    assert repository.delivery.hook_id == 456
    assert repository.payload == {
        "event_type": "push",
        "action": "created",
        "github_repository_id": 101,
    }


def test_webhook_service_does_not_process_an_invalid_signature():
    repository = FakeRepository()
    service = GitHubWebhookService(GitHubWebhookSettings("secret"), repository)

    with pytest.raises(GitHubWebhookError, match="signature"):
        asyncio.run(service.handle(b"{}", "sha256=bad", "delivery-1", "push", "456"))

    assert not hasattr(repository, "delivery")