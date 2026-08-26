from dataclasses import dataclass
from typing import Protocol

from .states import EvidenceValidity

REASON_LINKED_EVIDENCE_VERSION_CHANGED = "linked_evidence_version_changed"


@dataclass(frozen=True)
class AffectedClaimRevision:
    claim_revision_id: str
    evidence_version_id: str


@dataclass(frozen=True)
class FreshnessAssessmentDraft:
    claim_revision_id: str
    status: EvidenceValidity
    reason_code: str


class RevalidationRepository(Protocol):
    async def find_affected_claim_revisions(
        self,
        profile_id: str,
        source_artifact_id: str,
        changed_evidence_version_id: str,
    ) -> tuple[AffectedClaimRevision, ...]:
        """Return claim revisions linked to superseded versions of one source artifact."""

    async def record_freshness_assessment(
        self,
        profile_id: str,
        draft: FreshnessAssessmentDraft,
    ) -> str:
        """Append one freshness assessment without rewriting verification, review, or publication."""


class TargetedRevalidationService:
    """Flags claim revisions linked to superseded evidence without rewriting history."""

    def __init__(self, repository: RevalidationRepository) -> None:
        self._repository = repository

    async def revalidate_changed_artifact(
        self,
        profile_id: str,
        source_artifact_id: str,
        changed_evidence_version_id: str,
    ) -> tuple[str, ...]:
        affected = await self._repository.find_affected_claim_revisions(
            profile_id,
            source_artifact_id,
            changed_evidence_version_id,
        )
        assessment_ids = []
        for item in affected:
            assessment_id = await self._repository.record_freshness_assessment(
                profile_id,
                FreshnessAssessmentDraft(
                    claim_revision_id=item.claim_revision_id,
                    status=EvidenceValidity.STALE,
                    reason_code=REASON_LINKED_EVIDENCE_VERSION_CHANGED,
                ),
            )
            assessment_ids.append(assessment_id)
        return tuple(assessment_ids)
