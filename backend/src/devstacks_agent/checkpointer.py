from contextlib import asynccontextmanager
from os import getenv

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


class CheckpointerUnavailableError(RuntimeError):
    """Raised when SUPABASE_DB_URL is not configured."""


@asynccontextmanager
async def get_checkpointer():
    """Durable checkpointer for claim-extraction/verifier graphs, so an
    interrupted run replays from the same point after a worker restart."""
    conn_string = getenv("SUPABASE_DB_URL", "")
    if not conn_string:
        raise CheckpointerUnavailableError("SUPABASE_DB_URL is required")
    async with AsyncPostgresSaver.from_conn_string(conn_string) as checkpointer:
        # Idempotent (CREATE TABLE IF NOT EXISTS-style); cheap enough to call
        # every run rather than requiring a separate manual migration step.
        await checkpointer.setup()
        yield checkpointer


def thread_id_for(profile_id: str, source_artifact_id: str, evidence_version_id: str) -> str:
    """Stable per-ingestion-event thread id so replays after interrupt/restart
    are idempotent, per the project's HITL requirement."""
    return f"claim-extraction:{profile_id}:{source_artifact_id}:{evidence_version_id}"
