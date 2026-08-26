import asyncio

from cryptography.fernet import Fernet

from devstacks_api.github_evidence import GitHubEvidenceIngestionService, GitHubEvidenceWrite
from devstacks_api.github_ingestion import GitHubArtifact, GitHubCollection, GitHubCollectionOutcome
from devstacks_api.github_worker import GitHubIngestionWorker
from devstacks_api.repositories import IngestionRunLease
from devstacks_domain import EvidenceVersionOutcome, FernetTokenCipher, IngestionStatus


class FakeJobs:
    def __init__(self, lease: IngestionRunLease | None) -> None:
        self.lease = lease
        self.completed: tuple[IngestionRunLease, IngestionStatus, str | None] | None = None
        self.claimed_with_lease_seconds: int | None = None

    async def claim(self, worker_id: str, lease_seconds: int = 60) -> IngestionRunLease | None:
        assert worker_id == "worker-1"
        self.claimed_with_lease_seconds = lease_seconds
        return self.lease

    async def complete(self, lease, status, error_summary=None) -> None:
        self.completed = (lease, status, error_summary)


class FakeEvidenceRepository:
    async def get_access_token_encrypted(self, profile_id: str, connection_id: str) -> str:
        return self.encrypted_token

    async def append_evidence(self, profile_id, connection_id, artifact, content_hash_value):
        return GitHubEvidenceWrite(
            EvidenceVersionOutcome.CREATE_VERSION,
            1,
            source_artifact_id="artifact-1",
            evidence_version_id="version-1",
        )


class FakeCollector:
    async def collect(self) -> GitHubCollection:
        return GitHubCollection(
            (
                GitHubArtifact(
                    "github_repository",
                    "github:repository:1",
                    {"github_id": 1},
                    "2026-08-26T00:00:00Z",
                ),
            ),
            GitHubCollectionOutcome.SUCCEEDED,
        )


def evidence_service() -> GitHubEvidenceIngestionService:
    cipher = FernetTokenCipher(Fernet.generate_key().decode("ascii"))
    repository = FakeEvidenceRepository()
    repository.encrypted_token = cipher.encrypt("access-token")
    return GitHubEvidenceIngestionService(
        repository,
        cipher,
        collector_factory=lambda token: FakeCollector(),
    )


def lease(connection_id: str | None = "connection-1") -> IngestionRunLease:
    return IngestionRunLease(
        id="run-1",
        profile_id="profile-1",
        connection_id=connection_id,
        attempt_count=1,
        lease_owner="worker-1",
        lease_expires_at="2026-08-26T00:01:00+00:00",
    )


def test_worker_claims_ingests_and_completes_a_github_run():
    jobs = FakeJobs(lease())
    result = asyncio.run(GitHubIngestionWorker(jobs, evidence_service()).run_once("worker-1"))

    assert result.status is IngestionStatus.SUCCEEDED
    assert jobs.completed is not None
    assert jobs.completed[1] is IngestionStatus.SUCCEEDED


def test_worker_defaults_to_a_lease_long_enough_for_a_real_repository():
    # A real repository's full history can take well over a minute to
    # collect; a short lease expires mid-run and fails the terminal
    # complete_ingestion_run call. Found via live testing.
    jobs = FakeJobs(lease())
    asyncio.run(GitHubIngestionWorker(jobs, evidence_service()).run_once("worker-1"))

    assert jobs.claimed_with_lease_seconds == 300


def test_worker_reports_no_work_without_completion():
    jobs = FakeJobs(None)
    result = asyncio.run(GitHubIngestionWorker(jobs, evidence_service()).run_once("worker-1"))

    assert result.run_id is None
    assert jobs.completed is None


def test_worker_fails_a_lease_without_a_connection():
    jobs = FakeJobs(lease(connection_id=None))
    result = asyncio.run(GitHubIngestionWorker(jobs, evidence_service()).run_once("worker-1"))

    assert result.status is IngestionStatus.FAILED
    assert jobs.completed is not None
    assert jobs.completed[2] == "GitHub ingestion run is missing a connection"