from dataclasses import dataclass
from typing import Callable, Protocol

from devstacks_domain import (
    AgentRunRepository,
    EvidenceVersionOutcome,
    FernetTokenCipher,
    IngestionStatus,
    TargetedRevalidationService,
    TokenCipherError,
    content_hash,
)

from .github_ingestion import GitHubArtifact, GitHubCollection, GitHubEvidenceCollector


class GitHubEvidenceServiceError(RuntimeError):
    """Raised when a GitHub evidence ingestion cannot complete safely."""


@dataclass(frozen=True)
class GitHubEvidenceWrite:
    outcome: EvidenceVersionOutcome
    version_number: int
    source_artifact_id: str
    evidence_version_id: str


@dataclass(frozen=True)
class GitHubIngestionResult:
    status: IngestionStatus
    created_versions: int
    no_op_versions: int


class GitHubEvidenceRepository(Protocol):
    async def get_access_token_encrypted(
        self,
        profile_id: str,
        connection_id: str,
    ) -> str:
        """Return an encrypted access token only for the active tenant connection."""

    async def append_evidence(
        self,
        profile_id: str,
        connection_id: str,
        artifact: GitHubArtifact,
        content_hash_value: str,
    ) -> GitHubEvidenceWrite:
        """Append a version or return an explicit no-op for a normalized artifact."""


class GitHubEvidenceIngestionService:
    def __init__(
        self,
        repository: GitHubEvidenceRepository,
        token_cipher: FernetTokenCipher,
        collector_factory: Callable[[str], GitHubEvidenceCollector] = GitHubEvidenceCollector,
        revalidation_service: TargetedRevalidationService | None = None,
        agent_run_repository: AgentRunRepository | None = None,
    ) -> None:
        self._repository = repository
        self._token_cipher = token_cipher
        self._collector_factory = collector_factory
        self._revalidation_service = revalidation_service
        self._agent_run_repository = agent_run_repository

    async def ingest(self, profile_id: str, connection_id: str) -> GitHubIngestionResult:
        encrypted_token = await self._repository.get_access_token_encrypted(
            profile_id,
            connection_id,
        )
        try:
            access_token = self._token_cipher.decrypt(encrypted_token)
        except TokenCipherError as error:
            raise GitHubEvidenceServiceError("GitHub credential cannot be decrypted") from error

        collection = await self._collector_factory(access_token).collect()
        created_versions = 0
        no_op_versions = 0
        for artifact in collection.artifacts:
            write = await self._repository.append_evidence(
                profile_id,
                connection_id,
                artifact,
                content_hash(artifact.payload),
            )
            if write.outcome is EvidenceVersionOutcome.CREATE_VERSION:
                created_versions += 1
                if self._revalidation_service is not None:
                    await self._revalidation_service.revalidate_changed_artifact(
                        profile_id,
                        write.source_artifact_id,
                        write.evidence_version_id,
                    )
                if self._agent_run_repository is not None:
                    # Cheap, synchronous queue write only — the LLM extraction
                    # itself runs later, out-of-band, in devstacks-claims-worker.
                    # Keeps ingestion's short lease window off the LLM latency path.
                    await self._agent_run_repository.enqueue(
                        profile_id,
                        write.source_artifact_id,
                        write.evidence_version_id,
                        f"claim-extraction:{write.evidence_version_id}",
                    )
            else:
                no_op_versions += 1

        if collection.outcome.value == IngestionStatus.PARTIAL.value:
            status = IngestionStatus.PARTIAL
        elif created_versions == 0:
            status = IngestionStatus.NO_OP
        else:
            status = IngestionStatus.SUCCEEDED
        return GitHubIngestionResult(
            status=status,
            created_versions=created_versions,
            no_op_versions=no_op_versions,
        )