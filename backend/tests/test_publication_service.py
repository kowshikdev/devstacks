import asyncio

import pytest

from devstacks_domain import (
    EvidenceValidity,
    ProvenanceError,
    PublicationContext,
    PublicationRequest,
    PublicationService,
    PublicationStatus,
    ReviewStatus,
    VerificationStatus,
)


def request(**overrides) -> PublicationRequest:
    defaults = dict(
        claim_revision_id="revision-1",
        verification_status=VerificationStatus.VERIFIED,
        review_status=ReviewStatus.APPROVED,
        evidence_version_ids=frozenset({"version-1"}),
        evidence_validity=frozenset({EvidenceValidity.CURRENT}),
        source_artifact_ids=frozenset({"artifact-1"}),
    )
    defaults.update(overrides)
    return PublicationRequest(**defaults)


def context(**overrides) -> PublicationContext:
    return PublicationContext(
        claim_revision_id="revision-1",
        verification_decision_id="verification-1",
        review_decision_id="review-1",
        request=request(**overrides),
    )


class FakePublicationRepository:
    def __init__(self) -> None:
        self.recorded: list[tuple] = []

    async def record_publication(
        self,
        profile_id,
        claim_revision_id,
        verification_decision_id,
        review_decision_id,
        policy_version_id,
        status,
        published_at,
        withdrawn_at,
    ):
        self.recorded.append(
            (
                profile_id,
                claim_revision_id,
                verification_decision_id,
                review_decision_id,
                policy_version_id,
                status,
                published_at,
                withdrawn_at,
            )
        )
        return "publication-1"


def test_publication_service_publishes_a_fully_provenanced_claim():
    repository = FakePublicationRepository()
    service = PublicationService(repository)

    publication_id = asyncio.run(
        service.publish("profile-1", context(), published_at="2026-08-26T00:00:00Z")
    )

    assert publication_id == "publication-1"
    assert repository.recorded == [
        (
            "profile-1",
            "revision-1",
            "verification-1",
            "review-1",
            None,
            PublicationStatus.PUBLISHED,
            "2026-08-26T00:00:00Z",
            None,
        )
    ]


def test_publication_service_rejects_an_unverified_claim():
    repository = FakePublicationRepository()
    service = PublicationService(repository)

    with pytest.raises(ProvenanceError):
        asyncio.run(
            service.publish(
                "profile-1",
                context(verification_status=VerificationStatus.UNVERIFIED),
                published_at="2026-08-26T00:00:00Z",
            )
        )
    assert repository.recorded == []


def test_publication_service_rejects_stale_evidence():
    repository = FakePublicationRepository()
    service = PublicationService(repository)

    with pytest.raises(ProvenanceError):
        asyncio.run(
            service.publish(
                "profile-1",
                context(evidence_validity=frozenset({EvidenceValidity.STALE})),
                published_at="2026-08-26T00:00:00Z",
            )
        )
    assert repository.recorded == []
