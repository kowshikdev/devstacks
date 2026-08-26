from dataclasses import dataclass
from typing import Protocol

from devstacks_domain import IngestionStatus

from .github_evidence import GitHubEvidenceIngestionService
from .repositories import IngestionRunLease


class GitHubIngestionJobRepository(Protocol):
    async def claim(self, worker_id: str, lease_seconds: int = 60) -> IngestionRunLease | None:
        """Claim one queued run for a worker-owned lease."""

    async def complete(
        self,
        lease: IngestionRunLease,
        status: IngestionStatus,
        error_summary: str | None = None,
    ) -> None:
        """Complete exactly the current worker's lease."""


@dataclass(frozen=True)
class GitHubWorkerResult:
    run_id: str | None
    status: IngestionStatus | None


class GitHubIngestionWorker:
    """Claims and executes one GitHub ingestion run through the Postgres lease boundary."""

    def __init__(
        self,
        job_repository: GitHubIngestionJobRepository,
        evidence_service: GitHubEvidenceIngestionService,
    ) -> None:
        self._job_repository = job_repository
        self._evidence_service = evidence_service

    async def run_once(self, worker_id: str) -> GitHubWorkerResult:
        lease = await self._job_repository.claim(worker_id)
        if lease is None:
            return GitHubWorkerResult(run_id=None, status=None)
        if lease.connection_id is None:
            await self._job_repository.complete(
                lease,
                IngestionStatus.FAILED,
                "GitHub ingestion run is missing a connection",
            )
            return GitHubWorkerResult(run_id=lease.id, status=IngestionStatus.FAILED)
        try:
            result = await self._evidence_service.ingest(
                lease.profile_id,
                lease.connection_id,
            )
        except Exception:
            await self._job_repository.complete(
                lease,
                IngestionStatus.FAILED,
                "GitHub ingestion failed",
            )
            return GitHubWorkerResult(run_id=lease.id, status=IngestionStatus.FAILED)
        await self._job_repository.complete(lease, result.status)
        return GitHubWorkerResult(run_id=lease.id, status=result.status)