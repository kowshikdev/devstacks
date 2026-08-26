import asyncio
from os import getenv
from socket import gethostname

from devstacks_domain import FernetTokenCipher, TargetedRevalidationService

from .github_evidence import GitHubEvidenceIngestionService
from .github_worker import GitHubIngestionWorker
from .repositories import (
    SupabaseGitHubEvidenceRepository,
    SupabaseIngestionJobRepository,
    SupabaseRevalidationRepository,
    SupabaseServiceSettings,
)


async def run_once() -> int:
    settings = SupabaseServiceSettings.from_environment()
    token_cipher = FernetTokenCipher(getenv("DEVSTACKS_ENCRYPTION_KEY", ""))
    worker_id = getenv("DEVSTACKS_WORKER_ID", gethostname())
    evidence_service = GitHubEvidenceIngestionService(
        SupabaseGitHubEvidenceRepository(settings),
        token_cipher,
        revalidation_service=TargetedRevalidationService(SupabaseRevalidationRepository(settings)),
    )
    result = await GitHubIngestionWorker(
        SupabaseIngestionJobRepository(settings),
        evidence_service,
    ).run_once(worker_id)
    return 0 if result.status is not None or result.run_id is None else 1


def main() -> None:
    raise SystemExit(asyncio.run(run_once()))