import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from devstacks_api.main import app
from devstacks_api.repositories import (
    PublishedClaimTrail,
    PublishedEvidence,
    RepositoryUnavailableError,
    SupabasePublicProfileRepository,
    SupabaseServiceSettings,
)


def _repository(handler) -> SupabasePublicProfileRepository:
    return SupabasePublicProfileRepository(
        SupabaseServiceSettings(
            url="https://project.supabase.co",
            service_role_key="server-only-key",
        ),
        transport=httpx.MockTransport(handler),
    )


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "profile_id": "profile-1",
        "handle": "devstacks",
        "display_name": "Dev Stacks",
        "claim_revision_id": "claim-revision-1",
        "category": "contribution",
        "statement": "Published claim only.",
        "verification_status": "verified",
        "verifier_score": 0.94,
        "verified_at": "2026-08-26T00:00:00+00:00",
        "freshness_status": "current",
        "published_at": "2026-08-26T01:00:00+00:00",
        "evidence_version_id": "evidence-1",
        "relation": "supports",
        "source_type": "github.commit",
        "content_hash": "d3b07384d113edec49eaa6238ad5ff00",
        "version_number": 2,
        "connector_version": "github@1.4.0",
        "assurance_class": "provider_observed",
        "validity": "current",
        "observed_at": "2026-08-25T00:00:00+00:00",
    }
    row.update(overrides)
    return row


def test_repository_calls_only_the_server_projection_rpc():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/get_published_claim_evidence"
        assert request.headers["apikey"] == "server-only-key"
        assert json.loads(request.content) == {
            "p_handle": "devstacks",
            "p_claim_revision_id": "claim-revision-1",
        }
        return httpx.Response(200, json=[_row()])

    trail = asyncio.run(
        _repository(handler).get_published_claim_trail("devstacks", "claim-revision-1")
    )

    assert trail is not None
    assert trail.statement == "Published claim only."
    assert trail.verifier_score == pytest.approx(0.94)
    assert len(trail.evidence) == 1
    assert trail.evidence[0].content_hash == "d3b07384d113edec49eaa6238ad5ff00"


def test_repository_groups_every_linked_evidence_version():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                _row(),
                _row(
                    evidence_version_id="evidence-2",
                    relation="contradicts",
                    source_type="github.pull_request",
                    content_hash="c157a79031e1c40f85931829bc5fc552",
                ),
            ],
        )

    trail = asyncio.run(
        _repository(handler).get_published_claim_trail("devstacks", "claim-revision-1")
    )

    assert trail is not None
    assert [item.relation for item in trail.evidence] == ["supports", "contradicts"]


def test_repository_returns_an_empty_trail_for_a_claim_without_links():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                _row(
                    evidence_version_id=None,
                    relation=None,
                    source_type=None,
                    content_hash=None,
                    version_number=None,
                    connector_version=None,
                    assurance_class=None,
                    validity=None,
                    observed_at=None,
                )
            ],
        )

    trail = asyncio.run(
        _repository(handler).get_published_claim_trail("devstacks", "claim-revision-1")
    )

    assert trail is not None
    assert trail.evidence == ()


def test_repository_reads_a_numeric_score_rendered_as_a_string():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[_row(verifier_score="0.812")])

    trail = asyncio.run(
        _repository(handler).get_published_claim_trail("devstacks", "claim-revision-1")
    )

    assert trail is not None
    assert trail.verifier_score == pytest.approx(0.812)


def test_repository_returns_none_for_an_unpublished_claim():
    trail = asyncio.run(
        _repository(lambda request: httpx.Response(200, json=[])).get_published_claim_trail(
            "devstacks", "claim-revision-1"
        )
    )

    assert trail is None


def test_repository_rejects_a_response_for_another_handle():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[_row(handle="someone-else")])

    with pytest.raises(RepositoryUnavailableError):
        asyncio.run(
            _repository(handler).get_published_claim_trail("devstacks", "claim-revision-1")
        )


def test_repository_rejects_an_incomplete_evidence_record():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[_row(content_hash=None)])

    with pytest.raises(RepositoryUnavailableError):
        asyncio.run(
            _repository(handler).get_published_claim_trail("devstacks", "claim-revision-1")
        )


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={"message": "boom"}),
        httpx.Response(200, json={"unexpected": "shape"}),
    ],
)
def test_repository_rejects_unusable_responses(response: httpx.Response):
    with pytest.raises(RepositoryUnavailableError):
        asyncio.run(
            _repository(lambda request: response).get_published_claim_trail(
                "devstacks", "claim-revision-1"
            )
        )


TRAIL = PublishedClaimTrail(
    handle="devstacks",
    display_name="Dev Stacks",
    claim_revision_id="claim-revision-1",
    category="contribution",
    statement="Published claim only.",
    verification_status="verified",
    verifier_score=0.94,
    verified_at="2026-08-26T00:00:00+00:00",
    freshness_status="current",
    published_at="2026-08-26T01:00:00+00:00",
    evidence=(
        PublishedEvidence(
            evidence_version_id="evidence-1",
            relation="supports",
            source_type="github.commit",
            content_hash="d3b07384d113edec49eaa6238ad5ff00",
            version_number=2,
            connector_version="github@1.4.0",
            assurance_class="provider_observed",
            validity="current",
            observed_at="2026-08-25T00:00:00+00:00",
        ),
    ),
)


class FakePublicProfileRepository:
    def __init__(self, trail: PublishedClaimTrail | None) -> None:
        self._trail = trail

    async def get_published_profile(self, handle: str):
        raise AssertionError("the claim endpoint must not read the profile projection")

    async def get_published_claim_trail(self, handle: str, claim_revision_id: str):
        assert handle == "devstacks"
        assert claim_revision_id == "claim-revision-1"
        return self._trail


def test_claim_endpoint_needs_no_bearer_token_and_projects_the_trail():
    app.state.public_profile_repository = FakePublicProfileRepository(TRAIL)
    try:
        response = TestClient(app).get(
            "/v1/public/profiles/devstacks/claims/claim-revision-1"
        )
    finally:
        del app.state.public_profile_repository

    assert response.status_code == 200
    body = response.json()
    assert body["statement"] == "Published claim only."
    assert body["verifier_score"] == pytest.approx(0.94)
    assert body["evidence"] == [
        {
            "evidence_version_id": "evidence-1",
            "relation": "supports",
            "source_type": "github.commit",
            "content_hash": "d3b07384d113edec49eaa6238ad5ff00",
            "version_number": 2,
            "connector_version": "github@1.4.0",
            "assurance_class": "provider_observed",
            "validity": "current",
            "observed_at": "2026-08-25T00:00:00+00:00",
        }
    ]


def test_claim_endpoint_never_exposes_payloads_or_source_references():
    app.state.public_profile_repository = FakePublicProfileRepository(TRAIL)
    try:
        response = TestClient(app).get(
            "/v1/public/profiles/devstacks/claims/claim-revision-1"
        )
    finally:
        del app.state.public_profile_repository

    body = response.text.lower()
    assert "canonical_payload" not in body
    assert "source_ref" not in body


def test_claim_endpoint_returns_not_found_for_an_unpublished_claim():
    app.state.public_profile_repository = FakePublicProfileRepository(None)
    try:
        response = TestClient(app).get(
            "/v1/public/profiles/devstacks/claims/claim-revision-1"
        )
    finally:
        del app.state.public_profile_repository

    assert response.status_code == 404
