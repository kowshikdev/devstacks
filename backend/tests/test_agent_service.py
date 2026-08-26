import asyncio

import pytest

import devstacks_agent.service as service_module
from devstacks_agent.service import ClaimExtractionAgentService
from devstacks_domain import AgentRunLease, AgentRunStatus, ClaimRevisionRecord, VerificationStatus


def lease(**overrides) -> AgentRunLease:
    defaults = dict(
        id="run-1",
        profile_id="profile-1",
        source_artifact_id="artifact-1",
        evidence_version_id="version-1",
        attempt_count=1,
        lease_owner="worker-1",
        lease_expires_at="2026-08-26T00:05:00+00:00",
    )
    defaults.update(overrides)
    return AgentRunLease(**defaults)


class FakeAgentRunRepository:
    def __init__(self) -> None:
        self.completed: list[tuple] = []

    async def enqueue(self, profile_id, source_artifact_id, evidence_version_id, idempotency_key):
        raise AssertionError("not used by the service")

    async def claim(self, worker_id, lease_seconds=300):
        raise AssertionError("not used by the service")

    async def complete(self, lease, status, error_summary=None):
        self.completed.append((lease.id, status, error_summary))

    async def get(self, profile_id, run_id):
        raise AssertionError("not used by the service")


class FakeClaimRepository:
    def __init__(self) -> None:
        self.created: list = []

    async def create_claim_revision(self, profile_id, candidate):
        self.created.append(candidate)
        return ClaimRevisionRecord(claim_id="claim-1", claim_revision_id="revision-1", revision_number=1)

    async def get_evidence_links(self, profile_id, claim_revision_id):
        raise AssertionError("not used by this test")

    async def get_evidence_version(self, profile_id, evidence_version_id):
        return {"evidence_version_id": evidence_version_id}


class FakeVerificationRepository:
    def __init__(self) -> None:
        self.recorded: list = []

    async def get_current_verification_status(self, profile_id, claim_revision_id):
        return VerificationStatus.UNVERIFIED

    async def record_verification_decision(
        self, profile_id, claim_revision_id, status, verifier_score, agent_run_id, rationale
    ):
        self.recorded.append((claim_revision_id, status, verifier_score, agent_run_id, rationale))
        return "decision-1"


class FakeAgent:
    def __init__(self, structured_response) -> None:
        self.structured_response = structured_response
        self.calls: list = []

    async def ainvoke(self, messages, config):
        self.calls.append((messages, config))
        return {"structured_response": self.structured_response}


class RaisingAgent:
    async def ainvoke(self, messages, config):
        raise RuntimeError("model call failed")


def service(claim_repository=None, verification_repository=None, agent_run_repository=None):
    return ClaimExtractionAgentService(
        agent_run_repository or FakeAgentRunRepository(),
        claim_repository or FakeClaimRepository(),
        verification_repository or FakeVerificationRepository(),
        claim_repository or FakeClaimRepository(),
    )


def test_run_fails_a_lease_missing_evidence_identifiers():
    agent_run_repository = FakeAgentRunRepository()
    outcome = asyncio.run(
        service(agent_run_repository=agent_run_repository).run(
            lease(source_artifact_id=None, evidence_version_id=None)
        )
    )

    assert outcome.claim_revision_ids == ()
    assert agent_run_repository.completed == [("run-1", AgentRunStatus.FAILED, "agent run is missing its source artifact or evidence version")]


def test_run_extracts_and_verifies_through_deterministic_services():
    claim_repository = FakeClaimRepository()
    verification_repository = FakeVerificationRepository()
    agent_run_repository = FakeAgentRunRepository()

    extractor = FakeAgent({"claims": [{"category": "contribution", "statement": "Shipped it.", "relation": "supports"}]})
    verifier = FakeAgent({"status": "verified", "verifier_score": 0.95, "rationale": "matches commit"})

    original_build_model = service_module.build_model
    original_build_extractor = service_module.build_extractor_agent
    original_build_verifier = service_module.build_verifier_agent
    service_module.build_model = lambda: object()
    service_module.build_extractor_agent = lambda *a, **k: extractor
    service_module.build_verifier_agent = lambda *a, **k: verifier
    try:
        outcome = asyncio.run(
            service(claim_repository, verification_repository, agent_run_repository).run(lease())
        )
    finally:
        service_module.build_model = original_build_model
        service_module.build_extractor_agent = original_build_extractor
        service_module.build_verifier_agent = original_build_verifier

    assert outcome.claim_revision_ids == ("revision-1",)
    assert outcome.verification_decision_ids == ("decision-1",)
    assert claim_repository.created[0].statement == "Shipped it."
    assert verification_repository.recorded[0][:2] == ("revision-1", VerificationStatus.VERIFIED)
    assert agent_run_repository.completed == [("run-1", AgentRunStatus.SUCCEEDED, None)]


def test_run_marks_the_lease_failed_and_reraises_on_model_error():
    agent_run_repository = FakeAgentRunRepository()
    original_build_model = service_module.build_model
    original_build_extractor = service_module.build_extractor_agent
    service_module.build_model = lambda: object()
    service_module.build_extractor_agent = lambda *a, **k: RaisingAgent()
    try:
        with pytest.raises(RuntimeError, match="model call failed"):
            asyncio.run(service(agent_run_repository=agent_run_repository).run(lease()))
    finally:
        service_module.build_model = original_build_model
        service_module.build_extractor_agent = original_build_extractor

    assert agent_run_repository.completed == [("run-1", AgentRunStatus.FAILED, "model call failed")]
