from dataclasses import dataclass
from typing import Protocol


class AgentRunStatus:
    """Terminal outcomes accepted by complete_agent_run. Kept as plain string
    constants (not a StrEnum in states.py) since agent_runs.status already has
    its own narrower DB check constraint distinct from IngestionStatus."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class AgentRunLease:
    id: str
    profile_id: str
    source_artifact_id: str | None
    evidence_version_id: str | None
    attempt_count: int
    lease_owner: str
    lease_expires_at: str


class AgentRunRepository(Protocol):
    async def enqueue(
        self,
        profile_id: str,
        source_artifact_id: str,
        evidence_version_id: str,
        idempotency_key: str,
    ) -> str:
        """Queue one claim-extraction agent run. Cheap, synchronous, idempotent."""

    async def claim(self, worker_id: str, lease_seconds: int = 300) -> AgentRunLease | None:
        """Claim one queued or expired-lease run for a worker-owned lease."""

    async def complete(
        self,
        lease: AgentRunLease,
        status: str,
        error_summary: str | None = None,
    ) -> None:
        """Complete exactly the current worker's lease with a terminal AgentRunStatus."""

    async def get(self, profile_id: str, run_id: str) -> dict[str, object] | None:
        """Return one agent run scoped to the profile, or None."""


__all__ = [
    "AgentRunLease",
    "AgentRunRepository",
    "AgentRunStatus",
]
