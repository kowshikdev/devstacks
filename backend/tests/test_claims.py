import asyncio

import pytest

from devstacks_domain import (
    CandidateClaimRevision,
    ClaimEvidenceLinkDraft,
    ClaimIntakeService,
    ClaimRevisionRecord,
    ReviewDecisionService,
    ReviewStatus,
    TransitionError,
    VerificationDecisionService,
    VerificationStatus,
)


def candidate() -> CandidateClaimRevision:
    return CandidateClaimRevision(
        category="contribution",
        statement="Shipped the GitHub evidence ingestion pipeline.",
        evidence_links=(ClaimEvidenceLinkDraft("version-1", "supports"),),
    )


def test_candidate_claim_revision_requires_a_category():
    with pytest.raises(ValueError, match="category"):
        CandidateClaimRevision(
            category="",
            statement="statement",
            evidence_links=(ClaimEvidenceLinkDraft("version-1", "supports"),),
        )


def test_candidate_claim_revision_requires_at_least_one_evidence_link():
    with pytest.raises(ValueError, match="evidence link"):
        CandidateClaimRevision(
            category="contribution",
            statement="statement",
            evidence_links=(),
        )


class FakeClaimRepository:
    def __init__(self) -> None:
        self.created: list[CandidateClaimRevision] = []
        self.evidence_links: dict[str, tuple[ClaimEvidenceLinkDraft, ...]] = {}

    async def create_claim_revision(self, profile_id, candidate):
        assert profile_id == "profile-1"
        self.created.append(candidate)
        return ClaimRevisionRecord(
            claim_id=candidate.claim_id or "claim-1",
            claim_revision_id=f"revision-{len(self.created)}",
            revision_number=len(self.created),
        )

    async def get_evidence_links(self, profile_id, claim_revision_id):
        assert profile_id == "profile-1"
        return self.evidence_links[claim_revision_id]


def test_claim_intake_submits_the_candidate_as_given():
    repository = FakeClaimRepository()
    service = ClaimIntakeService(repository)

    record = asyncio.run(service.submit_candidate("profile-1", candidate()))

    assert record.revision_number == 1
    assert repository.created == [candidate()]


class FakeVerificationRepository:
    def __init__(self, current_status: VerificationStatus) -> None:
        self.current_status = current_status
        self.recorded: list[tuple] = []

    async def get_current_verification_status(self, profile_id, claim_revision_id):
        assert (profile_id, claim_revision_id) == ("profile-1", "revision-1")
        return self.current_status

    async def record_verification_decision(
        self, profile_id, claim_revision_id, status, verifier_score, agent_run_id, rationale
    ):
        self.recorded.append((status, verifier_score, agent_run_id, rationale))
        return "decision-1"


def test_verification_decision_service_records_a_valid_transition():
    repository = FakeVerificationRepository(VerificationStatus.UNVERIFIED)
    service = VerificationDecisionService(repository)

    decision_id = asyncio.run(
        service.record(
            "profile-1",
            "revision-1",
            VerificationStatus.VERIFIED,
            verifier_score=0.92,
            agent_run_id="run-1",
            rationale="matches commit authorship",
        )
    )

    assert decision_id == "decision-1"
    assert repository.recorded == [
        (VerificationStatus.VERIFIED, 0.92, "run-1", "matches commit authorship")
    ]


def test_verification_decision_service_rejects_an_invalid_transition():
    repository = FakeVerificationRepository(VerificationStatus.VERIFIED)
    service = VerificationDecisionService(repository)

    with pytest.raises(TransitionError):
        asyncio.run(
            service.record("profile-1", "revision-1", VerificationStatus.VERIFIED)
        )
    assert repository.recorded == []


class FakeReviewRepository:
    def __init__(self, current_status: ReviewStatus) -> None:
        self.current_status = current_status
        self.recorded: list[tuple] = []

    async def get_current_review_status(self, profile_id, claim_revision_id):
        assert (profile_id, claim_revision_id) == ("profile-1", "revision-1")
        return self.current_status

    async def record_review_decision(self, profile_id, claim_revision_id, status, actor_user_id, note):
        self.recorded.append((status, actor_user_id, note))
        return "review-1"


def test_review_decision_service_records_a_valid_approval():
    review_repository = FakeReviewRepository(ReviewStatus.PENDING)
    service = ReviewDecisionService(review_repository, FakeClaimRepository())

    decision_id = asyncio.run(
        service.record(
            "profile-1",
            "revision-1",
            ReviewStatus.APPROVED,
            actor_user_id="user-1",
            note="looks right",
        )
    )

    assert decision_id == "review-1"
    assert review_repository.recorded == [(ReviewStatus.APPROVED, "user-1", "looks right")]


def test_review_decision_service_rejects_an_invalid_transition():
    review_repository = FakeReviewRepository(ReviewStatus.APPROVED)
    service = ReviewDecisionService(review_repository, FakeClaimRepository())

    with pytest.raises(TransitionError):
        asyncio.run(
            service.record("profile-1", "revision-1", ReviewStatus.REJECTED, actor_user_id="user-1")
        )
    assert review_repository.recorded == []


def test_review_decision_service_edit_creates_the_next_revision_with_prior_evidence():
    claim_repository = FakeClaimRepository()
    claim_repository.evidence_links["revision-1"] = (
        ClaimEvidenceLinkDraft("version-1", "supports"),
    )
    service = ReviewDecisionService(FakeReviewRepository(ReviewStatus.PENDING), claim_repository)

    record = asyncio.run(
        service.edit(
            "profile-1",
            "claim-1",
            "revision-1",
            "contribution",
            "Edited statement text.",
        )
    )

    assert record.revision_number == 1
    assert claim_repository.created[0].statement == "Edited statement text."
    assert claim_repository.created[0].evidence_links == (
        ClaimEvidenceLinkDraft("version-1", "supports"),
    )
    assert claim_repository.created[0].claim_id == "claim-1"
