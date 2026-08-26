from fastapi.testclient import TestClient

from devstacks_api.auth import AuthenticatedUser
from devstacks_api.main import app
from devstacks_domain import ClaimEvidenceLinkDraft, ClaimRevisionRecord, EvidenceValidity, ReviewStatus


class FakeVerifier:
    async def validate(self, access_token: str) -> AuthenticatedUser:
        return AuthenticatedUser(id="profile-1", email="developer@example.com")


class FakeClaimRepository:
    def __init__(self) -> None:
        self.evidence_links = {"revision-1": (ClaimEvidenceLinkDraft("version-1", "supports"),)}
        self.created: list = []

    async def list_pending(self, profile_id: str):
        assert profile_id == "profile-1"
        return ({"claim_revision_id": "revision-1", "statement": "Shipped GH-004."},)

    async def create_claim_revision(self, profile_id, candidate):
        assert profile_id == "profile-1"
        self.created.append(candidate)
        return ClaimRevisionRecord(
            claim_id=candidate.claim_id or "claim-1",
            claim_revision_id="revision-2",
            revision_number=2,
        )

    async def get_evidence_links(self, profile_id, claim_revision_id):
        assert profile_id == "profile-1"
        return self.evidence_links[claim_revision_id]


class FakeReviewRepository:
    def __init__(self, current_status: str = "pending") -> None:
        self.current_status = current_status
        self.recorded: list = []

    async def get_current_review_status(self, profile_id, claim_revision_id):
        assert profile_id == "profile-1"
        return ReviewStatus(self.current_status)

    async def record_review_decision(self, profile_id, claim_revision_id, status, actor_user_id, note):
        self.recorded.append((claim_revision_id, status, actor_user_id, note))
        return "review-1"


class FakePublicationRepository:
    def __init__(self, context: dict) -> None:
        self.context = context
        self.recorded: list = []

    async def get_publication_context(self, profile_id, claim_revision_id):
        assert profile_id == "profile-1"
        return self.context

    async def record_publication(self, *args, **kwargs):
        self.recorded.append((args, kwargs))
        return "publication-1"


class FakeAgentRunRepository:
    def __init__(self, run: dict | None) -> None:
        self.run = run

    async def get(self, profile_id, run_id):
        assert profile_id == "profile-1"
        return self.run


def test_list_pending_claims_requires_the_pending_filter():
    app.state.access_token_verifier = FakeVerifier()
    try:
        response = TestClient(app).get(
            "/v1/claims",
            headers={"Authorization": "Bearer user-access-token"},
        )
    finally:
        del app.state.access_token_verifier

    assert response.status_code == 400


def test_list_pending_claims_returns_the_tenants_pending_revisions():
    app.state.access_token_verifier = FakeVerifier()
    app.state.claim_repository = FakeClaimRepository()
    try:
        response = TestClient(app).get(
            "/v1/claims?review=pending",
            headers={"Authorization": "Bearer user-access-token"},
        )
    finally:
        del app.state.access_token_verifier
        del app.state.claim_repository

    assert response.status_code == 200
    assert response.json()["claims"][0]["claim_revision_id"] == "revision-1"


def test_approve_claim_revision_records_an_audited_decision():
    app.state.access_token_verifier = FakeVerifier()
    review_repository = FakeReviewRepository("pending")
    app.state.review_repository = review_repository
    app.state.claim_repository = FakeClaimRepository()
    try:
        response = TestClient(app).post(
            "/v1/claim-revisions/revision-1/approve",
            headers={"Authorization": "Bearer user-access-token"},
            json={"note": "looks right"},
        )
    finally:
        del app.state.access_token_verifier
        del app.state.review_repository
        del app.state.claim_repository

    assert response.status_code == 200
    assert response.json() == {"review_decision_id": "review-1"}
    assert review_repository.recorded == [("revision-1", ReviewStatus.APPROVED, "profile-1", "looks right")]


def test_approve_claim_revision_rejects_an_invalid_transition():
    app.state.access_token_verifier = FakeVerifier()
    app.state.review_repository = FakeReviewRepository("approved")
    app.state.claim_repository = FakeClaimRepository()
    try:
        response = TestClient(app).post(
            "/v1/claim-revisions/revision-1/reject",
            headers={"Authorization": "Bearer user-access-token"},
            json={},
        )
    finally:
        del app.state.access_token_verifier
        del app.state.review_repository
        del app.state.claim_repository

    assert response.status_code == 409


def test_edit_claim_revision_creates_the_next_revision():
    app.state.access_token_verifier = FakeVerifier()
    app.state.review_repository = FakeReviewRepository("pending")
    claim_repository = FakeClaimRepository()
    app.state.claim_repository = claim_repository
    try:
        response = TestClient(app).post(
            "/v1/claim-revisions/revision-1/edit",
            headers={"Authorization": "Bearer user-access-token"},
            json={"claim_id": "claim-1", "category": "contribution", "statement": "Edited."},
        )
    finally:
        del app.state.access_token_verifier
        del app.state.review_repository
        del app.state.claim_repository

    assert response.status_code == 200
    assert response.json()["revision_number"] == 2
    assert claim_repository.created[0].statement == "Edited."


def test_publish_claim_revision_rejects_a_claim_revision_without_verification():
    app.state.access_token_verifier = FakeVerifier()
    app.state.publication_repository = FakePublicationRepository({})
    try:
        response = TestClient(app).post(
            "/v1/claim-revisions/revision-1/publish",
            headers={"Authorization": "Bearer user-access-token"},
        )
    finally:
        del app.state.access_token_verifier
        del app.state.publication_repository

    assert response.status_code == 409


def test_publish_claim_revision_succeeds_with_complete_provenance():
    app.state.access_token_verifier = FakeVerifier()
    app.state.publication_repository = FakePublicationRepository(
        {
            "verification_decision_id": "verification-1",
            "verification_status": "verified",
            "review_decision_id": "review-1",
            "review_status": "approved",
            "evidence_version_ids": ["version-1"],
            "evidence_validity": [EvidenceValidity.CURRENT.value],
            "source_artifact_ids": ["artifact-1"],
        }
    )
    try:
        response = TestClient(app).post(
            "/v1/claim-revisions/revision-1/publish",
            headers={"Authorization": "Bearer user-access-token"},
        )
    finally:
        del app.state.access_token_verifier
        del app.state.publication_repository

    assert response.status_code == 200
    assert response.json() == {"publication_id": "publication-1"}


def test_get_run_returns_not_found_for_an_absent_run():
    app.state.access_token_verifier = FakeVerifier()
    app.state.agent_run_repository = FakeAgentRunRepository(None)
    try:
        response = TestClient(app).get(
            "/v1/runs/run-1",
            headers={"Authorization": "Bearer user-access-token"},
        )
    finally:
        del app.state.access_token_verifier
        del app.state.agent_run_repository

    assert response.status_code == 404


def test_get_run_returns_the_tenants_run():
    app.state.access_token_verifier = FakeVerifier()
    app.state.agent_run_repository = FakeAgentRunRepository({"id": "run-1", "status": "succeeded"})
    try:
        response = TestClient(app).get(
            "/v1/runs/run-1",
            headers={"Authorization": "Bearer user-access-token"},
        )
    finally:
        del app.state.access_token_verifier
        del app.state.agent_run_repository

    assert response.status_code == 200
    assert response.json() == {"id": "run-1", "status": "succeeded"}
