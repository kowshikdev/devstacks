from dataclasses import replace

import pytest

from devstacks_domain import (
    EvidenceValidity,
    PublicationRequest,
    ProvenanceError,
    ReviewStatus,
    VerificationStatus,
    validate_publication,
)


@pytest.fixture
def verified_request() -> PublicationRequest:
    return PublicationRequest(
        claim_revision_id="revision-1",
        verification_status=VerificationStatus.VERIFIED,
        review_status=ReviewStatus.APPROVED,
        evidence_version_ids=frozenset({"evidence-version-1"}),
        evidence_validity=frozenset({EvidenceValidity.CURRENT}),
        source_artifact_ids=frozenset({"artifact-1"}),
    )


def test_published_revision_requires_complete_current_provenance(verified_request):
    validate_publication(verified_request)


def test_publication_rejects_missing_evidence(verified_request):
    request = replace(verified_request, evidence_version_ids=frozenset())

    with pytest.raises(ProvenanceError, match="evidence version"):
        validate_publication(request)


def test_publication_rejects_stale_evidence(verified_request):
    request = replace(
        verified_request,
        evidence_validity=frozenset({EvidenceValidity.CURRENT, EvidenceValidity.STALE}),
    )

    with pytest.raises(ProvenanceError, match="current"):
        validate_publication(request)


def test_auto_publication_requires_opt_in_and_policy(verified_request):
    request = replace(verified_request, auto_publish=True)

    with pytest.raises(ProvenanceError, match="policy version"):
        validate_publication(request)


def test_auto_publication_accepts_policy_and_threshold(verified_request):
    request = replace(
        verified_request,
        auto_publish=True,
        user_opted_in=True,
        policy_version="policy-1",
        deterministic_policy_passed=True,
        verifier_score=0.98,
        minimum_verifier_score=0.95,
    )

    validate_publication(request)
