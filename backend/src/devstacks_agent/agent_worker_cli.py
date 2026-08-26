import asyncio
import sys
from os import getenv
from socket import gethostname

from devstacks_api.repositories import (
    SupabaseAgentRunRepository,
    SupabaseClaimRepository,
    SupabaseServiceSettings,
    SupabaseVerificationRepository,
)

from .checkpointer import get_checkpointer
from .service import ClaimExtractionAgentService


async def run_once() -> int:
    settings = SupabaseServiceSettings.from_environment()
    worker_id = getenv("DEVSTACKS_WORKER_ID", gethostname())
    agent_run_repository = SupabaseAgentRunRepository(settings)
    claim_repository = SupabaseClaimRepository(settings)
    verification_repository = SupabaseVerificationRepository(settings)

    lease = await agent_run_repository.claim(worker_id, lease_seconds=300)
    if lease is None:
        return 0

    async with get_checkpointer() as checkpointer:
        service = ClaimExtractionAgentService(
            agent_run_repository,
            claim_repository,
            verification_repository,
            claim_repository,  # SupabaseClaimRepository also implements EvidenceReader
            checkpointer,
        )
        try:
            await service.run(lease)
        except Exception:
            # service.run() has already marked the lease failed; swallow here
            # so the worker process exits cleanly rather than crashing.
            return 1
    return 0


def main() -> None:
    # psycopg's async mode cannot run on Windows' default ProactorEventLoop.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(asyncio.run(run_once()))
