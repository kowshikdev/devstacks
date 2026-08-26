from dataclasses import dataclass
from typing import FrozenSet

from .states import EvidenceValidity, ReviewStatus, VerificationStatus


class ProvenanceError(ValueError):
    """Raised when a claim revision cannot be published safely."""


@dataclass(frozen=True)
class PublicationRequest:
    claim_revision_id: str
    verification_status: VerificationStatus
    review_status: ReviewStatus
    evidence_version_ids: FrozenSet[str]
    evidence_validity: FrozenSet[EvidenceValidity]
    source_artifact_ids: FrozenSet[str]
    policy_version: str | None = None
    auto_publish: bool = False
    user_opted_in: bool = False
    deterministic_policy_passed: bool = False
    verifier_score: float | None = None
    minimum_verifier_score: float | None = None


def validate_publication(request: PublicationRequest) -> None:
    """Validate publication prerequisites without performing a database write."""
    if not request.claim_revision_id:
        raise ProvenanceError("claim revision is required")
    if not request.evidence_version_ids:
        raise ProvenanceError("at least one evidence version is required")
    if not request.source_artifact_ids:
        raise ProvenanceError("at least one source artifact is required")
    if request.verification_status is not VerificationStatus.VERIFIED:
        raise ProvenanceError("claim revision must be verified")
    if request.review_status is not ReviewStatus.APPROVED:
        raise ProvenanceError("claim revision must be approved")
    if request.evidence_validity != {EvidenceValidity.CURRENT}:
        raise ProvenanceError("all publication evidence must be current")

    if request.auto_publish:
        if not request.policy_version:
            raise ProvenanceError("auto-publication requires a policy version")
        if not request.user_opted_in:
            raise ProvenanceError("auto-publication requires user opt-in")
        if not request.deterministic_policy_passed:
            raise ProvenanceError("deterministic publication policy did not pass")
        if request.minimum_verifier_score is None or request.verifier_score is None:
            raise ProvenanceError("auto-publication requires a verifier threshold")
        if request.verifier_score < request.minimum_verifier_score:
            raise ProvenanceError("verifier score is below the publication threshold")
