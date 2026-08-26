import asyncio
import json

import httpx
import pytest

from devstacks_api.repositories import (
    RepositoryUnavailableError,
    SupabaseAgentRunRepository,
    SupabaseClaimRepository,
    SupabasePublicationRepository,
    SupabaseReviewRepository,
    SupabaseServiceSettings,
    SupabaseVerificationRepository,
)
from devstacks_domain import (
    CandidateClaimRevision,
    ClaimEvidenceLinkDraft,
    PublicationStatus,
    ReviewStatus,
    VerificationStatus,
)


def settings() -> SupabaseServiceSettings:
    return SupabaseServiceSettings(url="https://project.supabase.co", service_role_key="server-only-key")


def test_claim_repository_creates_a_revision_with_evidence_links():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/create_claim_revision"
        body = json.loads(request.content)
        assert body["p_evidence_links"] == [{"evidence_version_id": "version-1", "relation": "supports"}]
        return httpx.Response(
            200,
            json={"claim_id": "claim-1", "claim_revision_id": "revision-1", "revision_number": 1},
        )

    repository = SupabaseClaimRepository(settings(), transport=httpx.MockTransport(handler))
    record = asyncio.run(
        repository.create_claim_revision(
            "profile-1",
            CandidateClaimRevision(
                category="contribution",
                statement="Shipped GH-004.",
                evidence_links=(ClaimEvidenceLinkDraft("version-1", "supports"),),
            ),
        )
    )

    assert record.claim_id == "claim-1"
    assert record.revision_number == 1


def test_claim_repository_reads_evidence_links():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/get_claim_revision_evidence_links"
        return httpx.Response(200, json=[{"evidence_version_id": "version-1", "relation": "supports"}])

    repository = SupabaseClaimRepository(settings(), transport=httpx.MockTransport(handler))
    links = asyncio.run(repository.get_evidence_links("profile-1", "revision-1"))

    assert links == (ClaimEvidenceLinkDraft("version-1", "supports"),)


def test_verification_repository_defaults_to_unverified_when_no_decision_exists():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=None)

    repository = SupabaseVerificationRepository(settings(), transport=httpx.MockTransport(handler))
    status = asyncio.run(repository.get_current_verification_status("profile-1", "revision-1"))

    assert status is VerificationStatus.UNVERIFIED


def test_verification_repository_records_a_decision():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/record_verification_decision"
        return httpx.Response(200, json={"id": "decision-1"})

    repository = SupabaseVerificationRepository(settings(), transport=httpx.MockTransport(handler))
    decision_id = asyncio.run(
        repository.record_verification_decision(
            "profile-1", "revision-1", VerificationStatus.VERIFIED, 0.9, None, "rationale"
        )
    )

    assert decision_id == "decision-1"


def test_review_repository_defaults_to_pending_when_no_decision_exists():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=None)

    repository = SupabaseReviewRepository(settings(), transport=httpx.MockTransport(handler))
    status = asyncio.run(repository.get_current_review_status("profile-1", "revision-1"))

    assert status is ReviewStatus.PENDING


def test_review_repository_records_a_decision():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/record_review_decision"
        return httpx.Response(200, json={"id": "review-1"})

    repository = SupabaseReviewRepository(settings(), transport=httpx.MockTransport(handler))
    decision_id = asyncio.run(
        repository.record_review_decision(
            "profile-1", "revision-1", ReviewStatus.APPROVED, "user-1", "note"
        )
    )

    assert decision_id == "review-1"


def test_publication_repository_records_a_publication():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/record_publication"
        return httpx.Response(200, json={"id": "publication-1"})

    repository = SupabasePublicationRepository(settings(), transport=httpx.MockTransport(handler))
    publication_id = asyncio.run(
        repository.record_publication(
            "profile-1",
            "revision-1",
            "verification-1",
            "review-1",
            None,
            PublicationStatus.PUBLISHED,
            "2026-08-26T00:00:00Z",
            None,
        )
    )

    assert publication_id == "publication-1"


def test_agent_run_repository_enqueues_a_run():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/enqueue_claim_agent_run"
        return httpx.Response(200, json={"id": "run-1"})

    repository = SupabaseAgentRunRepository(settings(), transport=httpx.MockTransport(handler))
    run_id = asyncio.run(
        repository.enqueue("profile-1", "artifact-1", "version-1", "idempotency-key-1")
    )

    assert run_id == "run-1"


def test_agent_run_repository_claims_a_lease():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/claim_agent_run"
        return httpx.Response(
            200,
            json={
                "id": "run-1",
                "profile_id": "profile-1",
                "source_artifact_id": "artifact-1",
                "evidence_version_id": "version-1",
                "attempt_count": 1,
                "lease_owner": "worker-1",
                "lease_expires_at": "2026-08-26T00:05:00+00:00",
            },
        )

    repository = SupabaseAgentRunRepository(settings(), transport=httpx.MockTransport(handler))
    lease = asyncio.run(repository.claim("worker-1"))

    assert lease is not None
    assert lease.id == "run-1"
    assert lease.lease_owner == "worker-1"


def test_agent_run_repository_claim_returns_none_without_work():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=None)

    repository = SupabaseAgentRunRepository(settings(), transport=httpx.MockTransport(handler))
    lease = asyncio.run(repository.claim("worker-1"))

    assert lease is None


def test_agent_run_repository_rejects_a_lease_from_another_worker():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "run-1",
                "profile_id": "profile-1",
                "source_artifact_id": None,
                "evidence_version_id": None,
                "attempt_count": 1,
                "lease_owner": "someone-else",
                "lease_expires_at": "2026-08-26T00:05:00+00:00",
            },
        )

    repository = SupabaseAgentRunRepository(settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(RepositoryUnavailableError, match="scope"):
        asyncio.run(repository.claim("worker-1"))
