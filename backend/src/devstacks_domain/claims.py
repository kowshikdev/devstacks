from dataclasses import dataclass
from typing import Protocol

from .states import ReviewStatus, VerificationStatus
from .transitions import (
    REVIEW_TRANSITIONS,
    VERIFICATION_TRANSITIONS,
    validate_transition,
)


@dataclass(frozen=True)
class ClaimEvidenceLinkDraft:
    evidence_version_id: str
    relation: str


@dataclass(frozen=True)
class CandidateClaimRevision:
    category: str
    statement: str
    evidence_links: tuple[ClaimEvidenceLinkDraft, ...]
    claim_id: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None

    def __post_init__(self) -> None:
        if not self.category.strip():
            raise ValueError("claim category is required")
        if not self.statement.strip():
            raise ValueError("claim statement is required")
        if not self.evidence_links:
            raise ValueError("at least one evidence link is required")


@dataclass(frozen=True)
class ClaimRevisionRecord:
    claim_id: str
    claim_revision_id: str
    revision_number: int


class ClaimRepository(Protocol):
    async def create_claim_revision(
        self,
        profile_id: str,
        candidate: CandidateClaimRevision,
    ) -> ClaimRevisionRecord:
        """Create the claim (if new) and its next immutable revision with evidence links."""

    async def get_evidence_links(
        self,
        profile_id: str,
        claim_revision_id: str,
    ) -> tuple[ClaimEvidenceLinkDraft, ...]:
        """Return the evidence links carried by one existing claim revision."""


class VerificationRepository(Protocol):
    async def get_current_verification_status(
        self,
        profile_id: str,
        claim_revision_id: str,
    ) -> VerificationStatus:
        """Return the latest verification status, or UNVERIFIED if none exists yet."""

    async def record_verification_decision(
        self,
        profile_id: str,
        claim_revision_id: str,
        status: VerificationStatus,
        verifier_score: float | None,
        agent_run_id: str | None,
        rationale: str | None,
    ) -> str:
        """Append one verification decision. Never called with an unvalidated transition."""


class ReviewRepository(Protocol):
    async def get_current_review_status(
        self,
        profile_id: str,
        claim_revision_id: str,
    ) -> ReviewStatus:
        """Return the latest review status, or PENDING if no decision exists yet."""

    async def record_review_decision(
        self,
        profile_id: str,
        claim_revision_id: str,
        status: ReviewStatus,
        actor_user_id: str,
        note: str | None,
    ) -> str:
        """Append one human review decision. Never called with an unvalidated transition."""


class ClaimIntakeService:
    """Turns extractor output into an immutable claim revision. No transition to validate:
    a brand-new revision always starts at UNVERIFIED/PENDING by the absence of any decision."""

    def __init__(self, repository: ClaimRepository) -> None:
        self._repository = repository

    async def submit_candidate(
        self,
        profile_id: str,
        candidate: CandidateClaimRevision,
    ) -> ClaimRevisionRecord:
        return await self._repository.create_claim_revision(profile_id, candidate)


class VerificationDecisionService:
    def __init__(self, repository: VerificationRepository) -> None:
        self._repository = repository

    async def record(
        self,
        profile_id: str,
        claim_revision_id: str,
        target_status: VerificationStatus,
        verifier_score: float | None = None,
        agent_run_id: str | None = None,
        rationale: str | None = None,
    ) -> str:
        current = await self._repository.get_current_verification_status(
            profile_id,
            claim_revision_id,
        )
        validate_transition(
            current=current,
            target=target_status,
            transitions=VERIFICATION_TRANSITIONS,
        )
        return await self._repository.record_verification_decision(
            profile_id,
            claim_revision_id,
            target_status,
            verifier_score,
            agent_run_id,
            rationale,
        )


class ReviewDecisionService:
    """Review is always a deterministic, audited human action — never agent-driven."""

    def __init__(
        self,
        review_repository: ReviewRepository,
        claim_repository: ClaimRepository,
    ) -> None:
        self._review_repository = review_repository
        self._claim_repository = claim_repository

    async def record(
        self,
        profile_id: str,
        claim_revision_id: str,
        target_status: ReviewStatus,
        actor_user_id: str,
        note: str | None = None,
    ) -> str:
        current = await self._review_repository.get_current_review_status(
            profile_id,
            claim_revision_id,
        )
        validate_transition(
            current=current,
            target=target_status,
            transitions=REVIEW_TRANSITIONS,
        )
        return await self._review_repository.record_review_decision(
            profile_id,
            claim_revision_id,
            target_status,
            actor_user_id,
            note,
        )

    async def edit(
        self,
        profile_id: str,
        claim_id: str,
        claim_revision_id: str,
        category: str,
        new_statement: str,
    ) -> ClaimRevisionRecord:
        """A reviewer edit is never a mutation: it creates the next immutable revision,
        carrying forward the prior revision's evidence links."""
        evidence_links = await self._claim_repository.get_evidence_links(
            profile_id,
            claim_revision_id,
        )
        candidate = CandidateClaimRevision(
            category=category,
            statement=new_statement,
            evidence_links=evidence_links,
            claim_id=claim_id,
        )
        return await self._claim_repository.create_claim_revision(profile_id, candidate)
