import asyncio

from cryptography.fernet import Fernet

from devstacks_api.github_evidence import (
    GitHubEvidenceIngestionService,
    GitHubEvidenceWrite,
)
from devstacks_api.github_ingestion import (
    GitHubArtifact,
    GitHubCollection,
    GitHubCollectionOutcome,
)
from devstacks_domain import (
    EvidenceVersionOutcome,
    FernetTokenCipher,
    IngestionStatus,
    TargetedRevalidationService,
)


class FakeRepository:
    async def get_access_token_encrypted(self, profile_id: str, connection_id: str) -> str:
        assert (profile_id, connection_id) == ("profile-1", "connection-1")
        return self.encrypted_token

    async def append_evidence(self, profile_id, connection_id, artifact, content_hash_value):
        assert (profile_id, connection_id) == ("profile-1", "connection-1")
        assert len(content_hash_value) == 64
        self.appended.append(artifact.source_ref)
        return GitHubEvidenceWrite(
            self.write_outcome,
            1,
            source_artifact_id="artifact-1",
            evidence_version_id="version-1",
        )


class FakeCollector:
    def __init__(self, collection: GitHubCollection) -> None:
        self._collection = collection

    async def collect(self) -> GitHubCollection:
        return self._collection


def artifact() -> GitHubArtifact:
    return GitHubArtifact(
        source_type="github_repository",
        source_ref="github:repository:1",
        payload={"github_id": 1, "full_name": "octocat/hello-world"},
        observed_at="2026-08-26T00:00:00Z",
    )


def test_evidence_service_decrypts_only_in_memory_and_appends_versions():
    cipher = FernetTokenCipher(Fernet.generate_key().decode("ascii"))
    repository = FakeRepository()
    repository.encrypted_token = cipher.encrypt("raw-access-token")
    repository.appended = []
    repository.write_outcome = EvidenceVersionOutcome.CREATE_VERSION
    service = GitHubEvidenceIngestionService(
        repository,
        cipher,
        collector_factory=lambda token: FakeCollector(
            GitHubCollection((artifact(),), GitHubCollectionOutcome.SUCCEEDED)
        ),
    )

    result = asyncio.run(service.ingest("profile-1", "connection-1"))

    assert repository.appended == ["github:repository:1"]
    assert result.status is IngestionStatus.SUCCEEDED
    assert result.created_versions == 1


def test_evidence_service_returns_no_op_when_every_observation_is_unchanged():
    cipher = FernetTokenCipher(Fernet.generate_key().decode("ascii"))
    repository = FakeRepository()
    repository.encrypted_token = cipher.encrypt("raw-access-token")
    repository.appended = []
    repository.write_outcome = EvidenceVersionOutcome.NO_OP
    service = GitHubEvidenceIngestionService(
        repository,
        cipher,
        collector_factory=lambda token: FakeCollector(
            GitHubCollection((artifact(),), GitHubCollectionOutcome.SUCCEEDED)
        ),
    )

    result = asyncio.run(service.ingest("profile-1", "connection-1"))

    assert result.status is IngestionStatus.NO_OP
    assert result.no_op_versions == 1


def test_evidence_service_preserves_a_partial_collection_outcome():
    cipher = FernetTokenCipher(Fernet.generate_key().decode("ascii"))
    repository = FakeRepository()
    repository.encrypted_token = cipher.encrypt("raw-access-token")
    repository.appended = []
    repository.write_outcome = EvidenceVersionOutcome.CREATE_VERSION
    service = GitHubEvidenceIngestionService(
        repository,
        cipher,
        collector_factory=lambda token: FakeCollector(
            GitHubCollection((artifact(),), GitHubCollectionOutcome.PARTIAL)
        ),
    )

    result = asyncio.run(service.ingest("profile-1", "connection-1"))

    assert result.status is IngestionStatus.PARTIAL


class FakeRevalidationRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def find_affected_claim_revisions(self, profile_id, source_artifact_id, changed_evidence_version_id):
        self.calls.append((profile_id, source_artifact_id, changed_evidence_version_id))
        return ()

    async def record_freshness_assessment(self, profile_id, draft):
        raise AssertionError("no affected claim revisions were returned")


def test_evidence_service_targets_revalidation_at_each_created_version():
    cipher = FernetTokenCipher(Fernet.generate_key().decode("ascii"))
    repository = FakeRepository()
    repository.encrypted_token = cipher.encrypt("raw-access-token")
    repository.appended = []
    repository.write_outcome = EvidenceVersionOutcome.CREATE_VERSION
    revalidation_repository = FakeRevalidationRepository()
    service = GitHubEvidenceIngestionService(
        repository,
        cipher,
        collector_factory=lambda token: FakeCollector(
            GitHubCollection((artifact(),), GitHubCollectionOutcome.SUCCEEDED)
        ),
        revalidation_service=TargetedRevalidationService(revalidation_repository),
    )

    asyncio.run(service.ingest("profile-1", "connection-1"))

    assert revalidation_repository.calls == [("profile-1", "artifact-1", "version-1")]


def test_evidence_service_skips_revalidation_for_a_no_op_write():
    cipher = FernetTokenCipher(Fernet.generate_key().decode("ascii"))
    repository = FakeRepository()
    repository.encrypted_token = cipher.encrypt("raw-access-token")
    repository.appended = []
    repository.write_outcome = EvidenceVersionOutcome.NO_OP
    revalidation_repository = FakeRevalidationRepository()
    service = GitHubEvidenceIngestionService(
        repository,
        cipher,
        collector_factory=lambda token: FakeCollector(
            GitHubCollection((artifact(),), GitHubCollectionOutcome.SUCCEEDED)
        ),
        revalidation_service=TargetedRevalidationService(revalidation_repository),
    )

    asyncio.run(service.ingest("profile-1", "connection-1"))

    assert revalidation_repository.calls == []

class FakeAgentRunRepository:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, str, str, str]] = []

    async def enqueue(self, profile_id, source_artifact_id, evidence_version_id, idempotency_key):
        self.enqueued.append((profile_id, source_artifact_id, evidence_version_id, idempotency_key))
        return "run-1"

    async def claim(self, worker_id, lease_seconds=300):
        raise AssertionError("not used by the ingestion service")

    async def complete(self, lease, status, error_summary=None):
        raise AssertionError("not used by the ingestion service")

    async def get(self, profile_id, run_id):
        raise AssertionError("not used by the ingestion service")


def test_evidence_service_enqueues_claim_extraction_for_each_created_version():
    cipher = FernetTokenCipher(Fernet.generate_key().decode("ascii"))
    repository = FakeRepository()
    repository.encrypted_token = cipher.encrypt("raw-access-token")
    repository.appended = []
    repository.write_outcome = EvidenceVersionOutcome.CREATE_VERSION
    agent_run_repository = FakeAgentRunRepository()
    service = GitHubEvidenceIngestionService(
        repository,
        cipher,
        collector_factory=lambda token: FakeCollector(
            GitHubCollection((artifact(),), GitHubCollectionOutcome.SUCCEEDED)
        ),
        agent_run_repository=agent_run_repository,
    )

    asyncio.run(service.ingest("profile-1", "connection-1"))

    assert agent_run_repository.enqueued == [
        ("profile-1", "artifact-1", "version-1", "claim-extraction:version-1")
    ]


def test_evidence_service_does_not_enqueue_claim_extraction_for_a_no_op_write():
    cipher = FernetTokenCipher(Fernet.generate_key().decode("ascii"))
    repository = FakeRepository()
    repository.encrypted_token = cipher.encrypt("raw-access-token")
    repository.appended = []
    repository.write_outcome = EvidenceVersionOutcome.NO_OP
    agent_run_repository = FakeAgentRunRepository()
    service = GitHubEvidenceIngestionService(
        repository,
        cipher,
        collector_factory=lambda token: FakeCollector(
            GitHubCollection((artifact(),), GitHubCollectionOutcome.SUCCEEDED)
        ),
        agent_run_repository=agent_run_repository,
    )

    asyncio.run(service.ingest("profile-1", "connection-1"))

    assert agent_run_repository.enqueued == []
