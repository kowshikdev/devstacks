import asyncio
import json

import httpx
import pytest

from devstacks_api.repositories import (
    RepositoryUnavailableError,
    SupabaseRevalidationRepository,
    SupabaseServiceSettings,
)
from devstacks_domain import EvidenceValidity, FreshnessAssessmentDraft


def repository(handler):
    return SupabaseRevalidationRepository(
        SupabaseServiceSettings(
            url="https://project.supabase.co",
            service_role_key="server-only-key",
        ),
        transport=httpx.MockTransport(handler),
    )


def test_find_affected_claim_revisions_calls_the_scoped_traversal_rpc():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/find_affected_claim_revisions"
        body = json.loads(request.content)
        assert body == {
            "p_profile_id": "profile-1",
            "p_source_artifact_id": "artifact-1",
            "p_changed_evidence_version_id": "version-2",
        }
        return httpx.Response(
            200,
            json=[
                {"claim_revision_id": "revision-1", "evidence_version_id": "version-1"},
            ],
        )

    affected = asyncio.run(
        repository(handler).find_affected_claim_revisions("profile-1", "artifact-1", "version-2")
    )

    assert len(affected) == 1
    assert affected[0].claim_revision_id == "revision-1"
    assert affected[0].evidence_version_id == "version-1"


def test_record_freshness_assessment_rejects_a_response_outside_the_tenant_scope():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/record_freshness_assessment"
        return httpx.Response(
            200,
            json={"id": "assessment-1", "claim_revision_id": "revision-1", "profile_id": "other-profile"},
        )

    with pytest.raises(RepositoryUnavailableError, match="scope"):
        asyncio.run(
            repository(handler).record_freshness_assessment(
                "profile-1",
                FreshnessAssessmentDraft(
                    claim_revision_id="revision-1",
                    status=EvidenceValidity.STALE,
                    reason_code="linked_evidence_version_changed",
                ),
            )
        )


def test_record_freshness_assessment_returns_the_assessment_id():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["p_status"] == "stale"
        return httpx.Response(
            200,
            json={"id": "assessment-1", "claim_revision_id": "revision-1", "profile_id": "profile-1"},
        )

    assessment_id = asyncio.run(
        repository(handler).record_freshness_assessment(
            "profile-1",
            FreshnessAssessmentDraft(
                claim_revision_id="revision-1",
                status=EvidenceValidity.STALE,
                reason_code="linked_evidence_version_changed",
            ),
        )
    )

    assert assessment_id == "assessment-1"
