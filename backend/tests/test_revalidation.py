import asyncio

from devstacks_domain import (
    AffectedClaimRevision,
    EvidenceValidity,
    FreshnessAssessmentDraft,
    TargetedRevalidationService,
)
from devstacks_domain.revalidation import REASON_LINKED_EVIDENCE_VERSION_CHANGED


class FakeRevalidationRepository:
    def __init__(self, affected: tuple[AffectedClaimRevision, ...]) -> None:
        self.affected = affected
        self.recorded: list[tuple[str, FreshnessAssessmentDraft]] = []

    async def find_affected_claim_revisions(
        self,
        profile_id: str,
        source_artifact_id: str,
        changed_evidence_version_id: str,
    ) -> tuple[AffectedClaimRevision, ...]:
        assert profile_id == "profile-1"
        assert source_artifact_id == "artifact-1"
        assert changed_evidence_version_id == "version-2"
        return self.affected

    async def record_freshness_assessment(
        self,
        profile_id: str,
        draft: FreshnessAssessmentDraft,
    ) -> str:
        self.recorded.append((profile_id, draft))
        return f"assessment-{len(self.recorded)}"


def test_revalidation_flags_every_claim_revision_linked_to_a_superseded_version():
    repository = FakeRevalidationRepository(
        (
            AffectedClaimRevision("revision-1", "version-1"),
            AffectedClaimRevision("revision-2", "version-1"),
        )
    )
    service = TargetedRevalidationService(repository)

    assessment_ids = asyncio.run(
        service.revalidate_changed_artifact("profile-1", "artifact-1", "version-2")
    )

    assert assessment_ids == ("assessment-1", "assessment-2")
    assert [draft.claim_revision_id for _, draft in repository.recorded] == [
        "revision-1",
        "revision-2",
    ]
    for _, draft in repository.recorded:
        assert draft.status is EvidenceValidity.STALE
        assert draft.reason_code == REASON_LINKED_EVIDENCE_VERSION_CHANGED


def test_revalidation_is_a_no_op_when_no_claim_revision_links_the_artifact():
    repository = FakeRevalidationRepository(())
    service = TargetedRevalidationService(repository)

    assessment_ids = asyncio.run(
        service.revalidate_changed_artifact("profile-1", "artifact-1", "version-2")
    )

    assert assessment_ids == ()
    assert repository.recorded == []
