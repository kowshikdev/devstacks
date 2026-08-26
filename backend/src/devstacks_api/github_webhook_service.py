from dataclasses import dataclass
from typing import Protocol

from devstacks_domain import TenantContext

from .github_webhooks import (
    GitHubWebhookDelivery,
    GitHubWebhookSettings,
    parse_delivery,
    verify_signature,
)


@dataclass(frozen=True)
class GitHubWebhookSubscriptionDraft:
    github_repository_id: int
    github_hook_id: int

    def __post_init__(self) -> None:
        if self.github_repository_id < 1 or self.github_hook_id < 1:
            raise ValueError("GitHub webhook identifiers must be positive")


@dataclass(frozen=True)
class GitHubWebhookSubscription:
    id: str
    profile_id: str
    connection_id: str
    github_repository_id: int
    github_hook_id: int


@dataclass(frozen=True)
class GitHubWebhookProcessingResult:
    ingestion_run_id: str | None
    is_duplicate: bool


class GitHubWebhookRepository(Protocol):
    async def register_subscription(
        self,
        tenant: TenantContext,
        connection_id: str,
        draft: GitHubWebhookSubscriptionDraft,
    ) -> GitHubWebhookSubscription:
        """Register a repository hook against one active tenant connection."""

    async def process_delivery(
        self,
        delivery: GitHubWebhookDelivery,
        payload: dict[str, object],
    ) -> GitHubWebhookProcessingResult | None:
        """Atomically deduplicate and queue a trusted delivery by hook ID."""


class GitHubWebhookService:
    def __init__(
        self,
        settings: GitHubWebhookSettings,
        repository: GitHubWebhookRepository,
    ) -> None:
        self._settings = settings
        self._repository = repository

    async def handle(
        self,
        raw_payload: bytes,
        signature: str | None,
        delivery_id: str | None,
        event_type: str | None,
        hook_id: str | None,
    ) -> GitHubWebhookProcessingResult | None:
        verify_signature(raw_payload, self._settings.secret, signature)
        delivery = parse_delivery(raw_payload, delivery_id, event_type, hook_id)
        return await self._repository.process_delivery(
            delivery,
            self._minimal_payload(delivery),
        )

    @staticmethod
    def _minimal_payload(delivery: GitHubWebhookDelivery) -> dict[str, object]:
        payload: dict[str, object] = {"event_type": delivery.event_type}
        action = delivery.payload.get("action")
        if isinstance(action, str):
            payload["action"] = action
        repository = delivery.payload.get("repository")
        if isinstance(repository, dict):
            repository_id = repository.get("id")
            if isinstance(repository_id, int) and not isinstance(repository_id, bool):
                payload["github_repository_id"] = repository_id
        return payload