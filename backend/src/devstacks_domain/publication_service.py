from dataclasses import dataclass
from typing import Protocol

from .publication import PublicationRequest, validate_publication
from .states import PublicationStatus


@dataclass(frozen=True)
class PublicationContext:
    """Current evidence/decision state a caller gathers before requesting publication.
    Kept distinct from PublicationRequest so the repository, not the caller, supplies
    the verification/review decision ids record_publication re-derives against."""

    claim_revision_id: str
    verification_decision_id: str
    review_decision_id: str | None
    request: PublicationRequest


class PublicationRepository(Protocol):
    async def record_publication(
        self,
        profile_id: str,
        claim_revision_id: str,
        verification_decision_id: str,
        review_decision_id: str | None,
        policy_version_id: str | None,
        status: PublicationStatus,
        published_at: str | None,
        withdrawn_at: str | None,
    ) -> str:
        """Append one publication record. RPC re-derives provenance as defense-in-depth."""


class PublicationService:
    """Wraps the existing pure validate_publication() with a repository write.
    Does not duplicate or modify publication.py's validation logic."""

    def __init__(self, repository: PublicationRepository) -> None:
        self._repository = repository

    async def publish(
        self,
        profile_id: str,
        context: PublicationContext,
        published_at: str,
        policy_version_id: str | None = None,
    ) -> str:
        validate_publication(context.request)
        return await self._repository.record_publication(
            profile_id,
            context.claim_revision_id,
            context.verification_decision_id,
            context.review_decision_id,
            policy_version_id,
            PublicationStatus.PUBLISHED,
            published_at,
            None,
        )
