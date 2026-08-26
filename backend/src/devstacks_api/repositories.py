from dataclasses import dataclass
from datetime import datetime
from os import getenv
from uuid import UUID

import httpx
from typing import Protocol

from devstacks_domain import TenantContext
from devstacks_domain import IngestionStatus
from devstacks_domain import (
    AffectedClaimRevision,
    FreshnessAssessmentDraft,
    RevalidationRepository,
)

from .github_oauth import (
    GitHubAuthorizationRepository,
    GitHubConnection,
    GitHubIdentity,
    GitHubOAuthAttempt,
    GitHubTokenExchange,
)
from .github_evidence import GitHubEvidenceRepository, GitHubEvidenceWrite
from .github_ingestion import GitHubArtifact
from .github_webhook_service import (
    GitHubWebhookProcessingResult,
    GitHubWebhookRepository,
    GitHubWebhookSubscription,
    GitHubWebhookSubscriptionDraft,
)
from devstacks_domain import EvidenceVersionOutcome, content_hash


class RepositoryUnavailableError(RuntimeError):
    """Raised when the Supabase data API cannot complete a repository request."""


@dataclass(frozen=True)
class ProfileSummary:
    id: str
    handle: str
    display_name: str | None
    is_public: bool


@dataclass(frozen=True)
class PublishedClaim:
    id: str
    category: str
    statement: str
    assurance_class: str | None
    freshness_status: str | None
    last_verified_at: str


@dataclass(frozen=True)
class PublishedProfile:
    id: str
    handle: str
    display_name: str | None
    claims: tuple[PublishedClaim, ...]


class ProfileRepository(Protocol):
    async def get_own_profile(self, tenant: TenantContext) -> ProfileSummary | None:
        """Return the profile for exactly one authenticated tenant."""


class PublicProfileRepository(Protocol):
    async def get_published_profile(self, handle: str) -> PublishedProfile | None:
        """Return a public projection containing published claims only."""


@dataclass(frozen=True)
class AuditEventDraft:
    event_type: str
    entity_type: str
    entity_id: str
    idempotency_key: str
    payload: dict[str, object]

    def __post_init__(self) -> None:
        if not self.event_type.strip() or not self.entity_type.strip():
            raise ValueError("audit event type and entity type are required")
        if not self.idempotency_key.strip():
            raise ValueError("audit event idempotency key is required")
        try:
            UUID(self.entity_id)
        except ValueError as error:
            raise ValueError("audit event entity id must be a UUID") from error


@dataclass(frozen=True)
class AuditEventRecord:
    id: str
    profile_id: str
    idempotency_key: str


@dataclass(frozen=True)
class IngestionRunLease:
    id: str
    profile_id: str
    connection_id: str | None
    attempt_count: int
    lease_owner: str
    lease_expires_at: str


@dataclass(frozen=True)
class ProviderEventDraft:
    connection_id: str
    provider_event_id: str
    event_type: str
    payload: dict[str, object]

    def __post_init__(self) -> None:
        try:
            UUID(self.connection_id)
        except ValueError as error:
            raise ValueError("provider event connection id must be a UUID") from error
        if not self.provider_event_id.strip() or not self.event_type.strip():
            raise ValueError("provider event id and type are required")


@dataclass(frozen=True)
class ProviderEventRecord:
    id: str
    profile_id: str
    connection_id: str
    provider_event_id: str


@dataclass(frozen=True)
class SupabaseServiceSettings:
    url: str
    service_role_key: str

    @classmethod
    def from_environment(cls) -> "SupabaseServiceSettings":
        url = getenv("SUPABASE_URL", "").rstrip("/")
        service_role_key = getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not service_role_key:
            raise RepositoryUnavailableError("Supabase service role is not configured")
        return cls(url=url, service_role_key=service_role_key)


class SupabaseProfileRepository:
    """Server-only repository for profile reads scoped by a validated tenant."""

    def __init__(
        self,
        settings: SupabaseServiceSettings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def get_own_profile(
        self,
        tenant: TenantContext,
    ) -> ProfileSummary | None:
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.url,
                headers={"apikey": self._settings.service_role_key},
                timeout=5.0,
                transport=self._transport,
            ) as client:
                response = await client.get(
                    "/rest/v1/profiles",
                    params={
                        "id": f"eq.{tenant.profile_id}",
                        "select": "id,handle,display_name,is_public",
                    },
                )
        except httpx.HTTPError as error:
            raise RepositoryUnavailableError("Supabase profile query failed") from error

        if response.is_error:
            raise RepositoryUnavailableError("Supabase profile query failed")

        records = response.json()
        if not isinstance(records, list):
            raise RepositoryUnavailableError("Supabase profile response is invalid")
        if not records:
            return None
        record = records[0]
        if not isinstance(record, dict):
            raise RepositoryUnavailableError("Supabase profile response is invalid")

        profile_id = record.get("id")
        handle = record.get("handle")
        is_public = record.get("is_public")
        if not isinstance(profile_id, str) or not isinstance(handle, str):
            raise RepositoryUnavailableError("Supabase profile response is incomplete")
        if profile_id != tenant.profile_id or not isinstance(is_public, bool):
            raise RepositoryUnavailableError("Supabase profile response violates tenant scope")

        display_name = record.get("display_name")
        return ProfileSummary(
            id=profile_id,
            handle=handle,
            display_name=display_name if isinstance(display_name, str) else None,
            is_public=is_public,
        )


class SupabasePublicProfileRepository:
    """Server-only reader for the narrowly scoped public profile projection."""

    def __init__(
        self,
        settings: SupabaseServiceSettings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def get_published_profile(self, handle: str) -> PublishedProfile | None:
        if not handle:
            return None
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.url,
                headers={"apikey": self._settings.service_role_key},
                timeout=5.0,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    "/rest/v1/rpc/get_published_profile",
                    json={"p_handle": handle},
                )
        except httpx.HTTPError as error:
            raise RepositoryUnavailableError("Supabase public profile query failed") from error
        if response.is_error:
            raise RepositoryUnavailableError("Supabase public profile query failed")
        try:
            records = response.json()
        except ValueError as error:
            raise RepositoryUnavailableError("Supabase public profile response is invalid") from error
        if not isinstance(records, list):
            raise RepositoryUnavailableError("Supabase public profile response is invalid")
        if not records:
            return None

        first = records[0]
        if not isinstance(first, dict):
            raise RepositoryUnavailableError("Supabase public profile response is invalid")
        profile_id = first.get("profile_id")
        profile_handle = first.get("handle")
        if not isinstance(profile_id, str) or profile_handle != handle:
            raise RepositoryUnavailableError("Supabase public profile response violates scope")
        display_name = first.get("display_name")
        claims = tuple(self._parse_published_claim(record, profile_id) for record in records)
        return PublishedProfile(
            id=profile_id,
            handle=profile_handle,
            display_name=display_name if isinstance(display_name, str) else None,
            claims=claims,
        )

    @staticmethod
    def _parse_published_claim(record: object, profile_id: str) -> PublishedClaim:
        if not isinstance(record, dict) or record.get("profile_id") != profile_id:
            raise RepositoryUnavailableError("Supabase public profile response violates scope")
        claim_id = record.get("claim_revision_id")
        category = record.get("category")
        statement = record.get("statement")
        last_verified_at = record.get("last_verified_at")
        if not all(isinstance(value, str) for value in (claim_id, category, statement, last_verified_at)):
            raise RepositoryUnavailableError("Supabase public profile response is incomplete")
        assurance_class = record.get("assurance_class")
        freshness_status = record.get("freshness_status")
        if assurance_class is not None and not isinstance(assurance_class, str):
            raise RepositoryUnavailableError("Supabase public profile response is invalid")
        if freshness_status is not None and not isinstance(freshness_status, str):
            raise RepositoryUnavailableError("Supabase public profile response is invalid")
        return PublishedClaim(
            id=claim_id,
            category=category,
            statement=statement,
            assurance_class=assurance_class,
            freshness_status=freshness_status,
            last_verified_at=last_verified_at,
        )


class SupabaseAuditRepository:
    """Append audit events with retry-safe idempotency under the server boundary."""

    def __init__(
        self,
        settings: SupabaseServiceSettings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def record(
        self,
        tenant: TenantContext,
        draft: AuditEventDraft,
    ) -> AuditEventRecord:
        record_payload = {
            "profile_id": tenant.profile_id,
            "event_type": draft.event_type,
            "entity_type": draft.entity_type,
            "entity_id": draft.entity_id,
            "idempotency_key": draft.idempotency_key,
            "payload": draft.payload,
        }
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.url,
                headers={
                    "apikey": self._settings.service_role_key,
                    "Prefer": "return=representation",
                },
                timeout=5.0,
                transport=self._transport,
            ) as client:
                response = await client.post("/rest/v1/audit_events", json=record_payload)
                if response.status_code == 409:
                    response = await client.get(
                        "/rest/v1/audit_events",
                        params={
                            "profile_id": f"eq.{tenant.profile_id}",
                            "idempotency_key": f"eq.{draft.idempotency_key}",
                            "select": "id,profile_id,idempotency_key",
                        },
                    )
        except httpx.HTTPError as error:
            raise RepositoryUnavailableError("Supabase audit write failed") from error

        if response.is_error:
            raise RepositoryUnavailableError("Supabase audit write failed")

        records = response.json()
        if not isinstance(records, list) or not records:
            raise RepositoryUnavailableError("Supabase audit response is invalid")
        record = records[0]
        if not isinstance(record, dict):
            raise RepositoryUnavailableError("Supabase audit response is invalid")

        event_id = record.get("id")
        profile_id = record.get("profile_id")
        idempotency_key = record.get("idempotency_key")
        if (
            not isinstance(event_id, str)
            or profile_id != tenant.profile_id
            or idempotency_key != draft.idempotency_key
        ):
            raise RepositoryUnavailableError("Supabase audit response violates tenant scope")
        return AuditEventRecord(
            id=event_id,
            profile_id=profile_id,
            idempotency_key=idempotency_key,
        )


class SupabaseIngestionJobRepository:
    """Server-only adapter for the transactional ingestion worker RPCs."""

    def __init__(
        self,
        settings: SupabaseServiceSettings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def claim(
        self,
        worker_id: str,
        lease_seconds: int = 60,
    ) -> IngestionRunLease | None:
        if not worker_id.strip():
            raise ValueError("worker id is required")
        if not 1 <= lease_seconds <= 3600:
            raise ValueError("lease seconds must be between 1 and 3600")
        payload = await self._call_rpc(
            "claim_ingestion_run",
            {"p_worker_id": worker_id, "p_lease_seconds": lease_seconds},
        )
        if payload is None:
            return None
        return self._parse_lease(payload, worker_id)

    async def complete(
        self,
        lease: IngestionRunLease,
        status: IngestionStatus,
        error_summary: str | None = None,
    ) -> None:
        if status not in {
            IngestionStatus.SUCCEEDED,
            IngestionStatus.PARTIAL,
            IngestionStatus.FAILED,
            IngestionStatus.NO_OP,
        }:
            raise ValueError("ingestion completion status must be terminal")
        payload = await self._call_rpc(
            "complete_ingestion_run",
            {
                "p_run_id": lease.id,
                "p_worker_id": lease.lease_owner,
                "p_status": status.value,
                "p_error_summary": error_summary,
            },
        )
        if not isinstance(payload, dict) or payload.get("id") != lease.id:
            raise RepositoryUnavailableError("Supabase completion response is invalid")

    async def enqueue_github(
        self,
        profile_id: str,
        connection_id: str,
        idempotency_key: str,
    ) -> str:
        if not idempotency_key.strip():
            raise ValueError("ingestion idempotency key is required")
        payload = await self._call_rpc(
            "enqueue_github_ingestion_run",
            {
                "p_profile_id": profile_id,
                "p_connection_id": connection_id,
                "p_idempotency_key": idempotency_key,
            },
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("id"), str):
            raise RepositoryUnavailableError("Supabase GitHub ingestion queue response is invalid")
        if payload.get("profile_id") != profile_id or payload.get("connection_id") != connection_id:
            raise RepositoryUnavailableError("Supabase GitHub ingestion queue response violates scope")
        return payload["id"]

    async def _call_rpc(self, name: str, payload: dict[str, object]) -> object:
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.url,
                headers={"apikey": self._settings.service_role_key},
                timeout=5.0,
                transport=self._transport,
            ) as client:
                response = await client.post(f"/rest/v1/rpc/{name}", json=payload)
        except httpx.HTTPError as error:
            raise RepositoryUnavailableError("Supabase ingestion RPC failed") from error

        if response.is_error:
            raise RepositoryUnavailableError("Supabase ingestion RPC failed")
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as error:
            raise RepositoryUnavailableError("Supabase ingestion RPC response is invalid") from error

    @staticmethod
    def _parse_lease(payload: object, worker_id: str) -> IngestionRunLease:
        if isinstance(payload, list):
            if len(payload) != 1:
                raise RepositoryUnavailableError("Supabase lease response is invalid")
            payload = payload[0]
        if not isinstance(payload, dict):
            raise RepositoryUnavailableError("Supabase lease response is invalid")

        run_id = payload.get("id")
        profile_id = payload.get("profile_id")
        connection_id = payload.get("connection_id")
        attempt_count = payload.get("attempt_count")
        lease_owner = payload.get("lease_owner")
        lease_expires_at = payload.get("lease_expires_at")
        if (
            not isinstance(run_id, str)
            or not isinstance(profile_id, str)
            or (connection_id is not None and not isinstance(connection_id, str))
            or not isinstance(attempt_count, int)
            or attempt_count < 1
            or lease_owner != worker_id
            or not isinstance(lease_expires_at, str)
        ):
            raise RepositoryUnavailableError("Supabase lease response violates worker scope")
        return IngestionRunLease(
            id=run_id,
            profile_id=profile_id,
            connection_id=connection_id,
            attempt_count=attempt_count,
            lease_owner=lease_owner,
            lease_expires_at=lease_expires_at,
        )


class SupabaseProviderEventRepository:
    """Server-only provider delivery recorder backed by the tenant-checking RPC."""

    def __init__(
        self,
        settings: SupabaseServiceSettings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def record(
        self,
        tenant: TenantContext,
        draft: ProviderEventDraft,
    ) -> ProviderEventRecord:
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.url,
                headers={"apikey": self._settings.service_role_key},
                timeout=5.0,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    "/rest/v1/rpc/record_provider_event",
                    json={
                        "p_profile_id": tenant.profile_id,
                        "p_connection_id": draft.connection_id,
                        "p_provider_event_id": draft.provider_event_id,
                        "p_event_type": draft.event_type,
                        "p_payload": draft.payload,
                    },
                )
        except httpx.HTTPError as error:
            raise RepositoryUnavailableError("Supabase provider event write failed") from error

        if response.is_error:
            raise RepositoryUnavailableError("Supabase provider event write failed")
        try:
            record = response.json()
        except ValueError as error:
            raise RepositoryUnavailableError("Supabase provider event response is invalid") from error
        if isinstance(record, list):
            if len(record) != 1:
                raise RepositoryUnavailableError("Supabase provider event response is invalid")
            record = record[0]
        if not isinstance(record, dict):
            raise RepositoryUnavailableError("Supabase provider event response is invalid")

        event_id = record.get("id")
        profile_id = record.get("profile_id")
        connection_id = record.get("connection_id")
        provider_event_id = record.get("provider_event_id")
        if (
            not isinstance(event_id, str)
            or profile_id != tenant.profile_id
            or connection_id != draft.connection_id
            or provider_event_id != draft.provider_event_id
        ):
            raise RepositoryUnavailableError("Supabase provider event response violates tenant scope")
        return ProviderEventRecord(
            id=event_id,
            profile_id=profile_id,
            connection_id=connection_id,
            provider_event_id=provider_event_id,
        )


class SupabaseGitHubAuthorizationRepository(GitHubAuthorizationRepository):
    """Server-only adapter for the GitHub OAuth state and credential RPCs."""

    def __init__(
        self,
        settings: SupabaseServiceSettings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def create_attempt(
        self,
        tenant: TenantContext,
        state_hash: str,
        code_verifier_encrypted: str,
        redirect_uri: str,
        expires_at: datetime,
    ) -> None:
        record = await self._call_rpc(
            "create_github_oauth_attempt",
            {
                "p_profile_id": tenant.profile_id,
                "p_state_hash": state_hash,
                "p_code_verifier_encrypted": code_verifier_encrypted,
                "p_redirect_uri": redirect_uri,
                "p_expires_at": expires_at.isoformat(),
            },
        )
        record = self._one_record(record, "Supabase GitHub OAuth attempt response is invalid")
        if record.get("profile_id") != tenant.profile_id:
            raise RepositoryUnavailableError("Supabase GitHub OAuth attempt violates tenant scope")

    async def consume_attempt(self, state_hash: str) -> GitHubOAuthAttempt | None:
        records = await self._call_rpc(
            "consume_github_oauth_attempt",
            {"p_state_hash": state_hash},
        )
        if records == []:
            return None
        record = self._one_record(records, "Supabase GitHub OAuth state response is invalid")
        profile_id = record.get("profile_id")
        code_verifier_encrypted = record.get("code_verifier_encrypted")
        redirect_uri = record.get("redirect_uri")
        if not all(
            isinstance(value, str) and value
            for value in (profile_id, code_verifier_encrypted, redirect_uri)
        ):
            raise RepositoryUnavailableError("Supabase GitHub OAuth state response is incomplete")
        return GitHubOAuthAttempt(
            profile_id=profile_id,
            code_verifier_encrypted=code_verifier_encrypted,
            redirect_uri=redirect_uri,
        )

    async def complete_authorization(
        self,
        attempt: GitHubOAuthAttempt,
        identity: GitHubIdentity,
        token_exchange: GitHubTokenExchange,
        access_token_encrypted: str,
        refresh_token_encrypted: str | None,
        access_token_expires_at: datetime | None,
        refresh_token_expires_at: datetime | None,
    ) -> GitHubConnection:
        record = await self._call_rpc(
            "complete_github_authorization",
            {
                "p_profile_id": attempt.profile_id,
                "p_github_subject_id": identity.subject_id,
                "p_github_login": identity.login,
                "p_access_token_encrypted": access_token_encrypted,
                "p_refresh_token_encrypted": refresh_token_encrypted,
                "p_access_token_expires_at": self._timestamp(access_token_expires_at),
                "p_refresh_token_expires_at": self._timestamp(refresh_token_expires_at),
                "p_scopes": list(token_exchange.scopes),
            },
        )
        record = self._one_record(record, "Supabase GitHub authorization response is invalid")
        connection_id = record.get("connection_id")
        source_subject_id = record.get("source_subject_id")
        if not isinstance(connection_id, str) or not isinstance(source_subject_id, str):
            raise RepositoryUnavailableError("Supabase GitHub authorization response is incomplete")
        return GitHubConnection(
            id=connection_id,
            source_subject_id=source_subject_id,
            login=identity.login,
        )

    async def _call_rpc(self, name: str, payload: dict[str, object]) -> object:
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.url,
                headers={"apikey": self._settings.service_role_key},
                timeout=5.0,
                transport=self._transport,
            ) as client:
                response = await client.post(f"/rest/v1/rpc/{name}", json=payload)
        except httpx.HTTPError as error:
            raise RepositoryUnavailableError("Supabase GitHub OAuth RPC failed") from error
        if response.is_error:
            raise RepositoryUnavailableError("Supabase GitHub OAuth RPC failed")
        try:
            return response.json()
        except ValueError as error:
            raise RepositoryUnavailableError("Supabase GitHub OAuth RPC response is invalid") from error

    @staticmethod
    def _one_record(payload: object, error_message: str) -> dict[str, object]:
        if isinstance(payload, list):
            if len(payload) != 1:
                raise RepositoryUnavailableError(error_message)
            payload = payload[0]
        if not isinstance(payload, dict):
            raise RepositoryUnavailableError(error_message)
        return payload

    @staticmethod
    def _timestamp(value: datetime | None) -> str | None:
        return value.isoformat() if value else None


class SupabaseGitHubEvidenceRepository(GitHubEvidenceRepository):
    """Server-only adapter for encrypted GitHub credential reads and evidence appends."""

    def __init__(
        self,
        settings: SupabaseServiceSettings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def get_access_token_encrypted(
        self,
        profile_id: str,
        connection_id: str,
    ) -> str:
        payload = await self._call_rpc(
            "get_github_connection_credential",
            {"p_profile_id": profile_id, "p_connection_id": connection_id},
        )
        if payload == []:
            raise RepositoryUnavailableError("Active GitHub connection was not found")
        record = self._one_record(payload, "Supabase GitHub credential response is invalid")
        access_token_encrypted = record.get("access_token_encrypted")
        if not isinstance(access_token_encrypted, str) or not access_token_encrypted:
            raise RepositoryUnavailableError("Supabase GitHub credential response is incomplete")
        return access_token_encrypted

    async def append_evidence(
        self,
        profile_id: str,
        connection_id: str,
        artifact: GitHubArtifact,
        content_hash_value: str,
    ) -> GitHubEvidenceWrite:
        payload = await self._call_rpc(
            "append_github_evidence_version",
            {
                "p_profile_id": profile_id,
                "p_connection_id": connection_id,
                "p_source_type": artifact.source_type,
                "p_source_ref": artifact.source_ref,
                "p_canonical_payload": artifact.payload,
                "p_content_hash": content_hash_value,
                "p_connector_version": "github-rest-v1",
                "p_observed_at": artifact.observed_at,
            },
        )
        record = self._one_record(payload, "Supabase GitHub evidence response is invalid")
        outcome = record.get("outcome")
        version_number = record.get("version_number")
        source_artifact_id = record.get("source_artifact_id")
        evidence_version_id = record.get("evidence_version_id")
        if (
            outcome not in {item.value for item in EvidenceVersionOutcome}
            or not isinstance(version_number, int)
            or not isinstance(source_artifact_id, str)
            or not isinstance(evidence_version_id, str)
        ):
            raise RepositoryUnavailableError("Supabase GitHub evidence response is incomplete")
        return GitHubEvidenceWrite(
            outcome=EvidenceVersionOutcome(outcome),
            version_number=version_number,
            source_artifact_id=source_artifact_id,
            evidence_version_id=evidence_version_id,
        )

    async def _call_rpc(self, name: str, payload: dict[str, object]) -> object:
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.url,
                headers={"apikey": self._settings.service_role_key},
                timeout=10.0,
                transport=self._transport,
            ) as client:
                response = await client.post(f"/rest/v1/rpc/{name}", json=payload)
        except httpx.HTTPError as error:
            raise RepositoryUnavailableError("Supabase GitHub evidence RPC failed") from error
        if response.is_error:
            raise RepositoryUnavailableError("Supabase GitHub evidence RPC failed")
        try:
            return response.json()
        except ValueError as error:
            raise RepositoryUnavailableError("Supabase GitHub evidence RPC response is invalid") from error

    @staticmethod
    def _one_record(payload: object, error_message: str) -> dict[str, object]:
        if isinstance(payload, list):
            if len(payload) != 1:
                raise RepositoryUnavailableError(error_message)
            payload = payload[0]
        if not isinstance(payload, dict):
            raise RepositoryUnavailableError(error_message)
        return payload


class SupabaseGitHubWebhookRepository(GitHubWebhookRepository):
    """Server-only adapter for GitHub webhook subscription and replay processing RPCs."""

    def __init__(
        self,
        settings: SupabaseServiceSettings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def register_subscription(
        self,
        tenant: TenantContext,
        connection_id: str,
        draft: GitHubWebhookSubscriptionDraft,
    ) -> GitHubWebhookSubscription:
        payload = await self._call_rpc(
            "register_github_webhook_subscription",
            {
                "p_profile_id": tenant.profile_id,
                "p_connection_id": connection_id,
                "p_github_repository_id": draft.github_repository_id,
                "p_github_hook_id": draft.github_hook_id,
            },
        )
        record = self._one_record(payload, "Supabase GitHub webhook subscription response is invalid")
        subscription_id = record.get("id")
        profile_id = record.get("profile_id")
        returned_connection_id = record.get("connection_id")
        repository_id = record.get("github_repository_id")
        hook_id = record.get("github_hook_id")
        if (
            not isinstance(subscription_id, str)
            or profile_id != tenant.profile_id
            or returned_connection_id != connection_id
            or repository_id != draft.github_repository_id
            or hook_id != draft.github_hook_id
        ):
            raise RepositoryUnavailableError("Supabase GitHub webhook subscription violates scope")
        return GitHubWebhookSubscription(
            id=subscription_id,
            profile_id=profile_id,
            connection_id=returned_connection_id,
            github_repository_id=repository_id,
            github_hook_id=hook_id,
        )

    async def process_delivery(
        self,
        delivery,
        payload: dict[str, object],
    ) -> GitHubWebhookProcessingResult | None:
        response = await self._call_rpc(
            "process_github_webhook_delivery",
            {
                "p_github_hook_id": delivery.hook_id,
                "p_provider_event_id": delivery.delivery_id,
                "p_event_type": delivery.event_type,
                "p_payload": payload,
            },
        )
        if response == []:
            return None
        record = self._one_record(response, "Supabase GitHub webhook delivery response is invalid")
        profile_id = record.get("profile_id")
        connection_id = record.get("connection_id")
        run_id = record.get("ingestion_run_id")
        is_duplicate = record.get("is_duplicate")
        if not isinstance(profile_id, str) or not isinstance(connection_id, str):
            raise RepositoryUnavailableError("Supabase GitHub webhook delivery response violates scope")
        if run_id is not None and not isinstance(run_id, str):
            raise RepositoryUnavailableError("Supabase GitHub webhook delivery response is invalid")
        if not isinstance(is_duplicate, bool):
            raise RepositoryUnavailableError("Supabase GitHub webhook delivery response is invalid")
        return GitHubWebhookProcessingResult(
            ingestion_run_id=run_id,
            is_duplicate=is_duplicate,
        )

    async def _call_rpc(self, name: str, payload: dict[str, object]) -> object:
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.url,
                headers={"apikey": self._settings.service_role_key},
                timeout=5.0,
                transport=self._transport,
            ) as client:
                response = await client.post(f"/rest/v1/rpc/{name}", json=payload)
        except httpx.HTTPError as error:
            raise RepositoryUnavailableError("Supabase GitHub webhook RPC failed") from error
        if response.is_error:
            raise RepositoryUnavailableError("Supabase GitHub webhook RPC failed")
        try:
            return response.json()
        except ValueError as error:
            raise RepositoryUnavailableError("Supabase GitHub webhook RPC response is invalid") from error

    @staticmethod
    def _one_record(payload: object, error_message: str) -> dict[str, object]:
        if isinstance(payload, list):
            if len(payload) != 1:
                raise RepositoryUnavailableError(error_message)
            payload = payload[0]
        if not isinstance(payload, dict):
            raise RepositoryUnavailableError(error_message)
        return payload

class SupabaseRevalidationRepository(RevalidationRepository):
    """Server-only adapter for affected-evidence traversal and freshness assessments."""

    def __init__(
        self,
        settings: SupabaseServiceSettings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def find_affected_claim_revisions(
        self,
        profile_id: str,
        source_artifact_id: str,
        changed_evidence_version_id: str,
    ) -> tuple[AffectedClaimRevision, ...]:
        payload = await self._call_rpc(
            "find_affected_claim_revisions",
            {
                "p_profile_id": profile_id,
                "p_source_artifact_id": source_artifact_id,
                "p_changed_evidence_version_id": changed_evidence_version_id,
            },
        )
        if not isinstance(payload, list):
            raise RepositoryUnavailableError("Supabase affected claim revisions response is invalid")
        affected = []
        for record in payload:
            if not isinstance(record, dict):
                raise RepositoryUnavailableError("Supabase affected claim revisions response is invalid")
            claim_revision_id = record.get("claim_revision_id")
            evidence_version_id = record.get("evidence_version_id")
            if not isinstance(claim_revision_id, str) or not isinstance(evidence_version_id, str):
                raise RepositoryUnavailableError("Supabase affected claim revisions response is incomplete")
            affected.append(
                AffectedClaimRevision(
                    claim_revision_id=claim_revision_id,
                    evidence_version_id=evidence_version_id,
                )
            )
        return tuple(affected)

    async def record_freshness_assessment(
        self,
        profile_id: str,
        draft: FreshnessAssessmentDraft,
    ) -> str:
        payload = await self._call_rpc(
            "record_freshness_assessment",
            {
                "p_profile_id": profile_id,
                "p_claim_revision_id": draft.claim_revision_id,
                "p_status": draft.status.value,
                "p_reason_code": draft.reason_code,
                "p_recheck_after": None,
            },
        )
        record = self._one_record(payload, "Supabase freshness assessment response is invalid")
        assessment_id = record.get("id")
        response_claim_revision_id = record.get("claim_revision_id")
        response_profile_id = record.get("profile_id")
        if (
            not isinstance(assessment_id, str)
            or response_claim_revision_id != draft.claim_revision_id
            or response_profile_id != profile_id
        ):
            raise RepositoryUnavailableError("Supabase freshness assessment response violates scope")
        return assessment_id

    async def _call_rpc(self, name: str, payload: dict[str, object]) -> object:
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.url,
                headers={"apikey": self._settings.service_role_key},
                timeout=5.0,
                transport=self._transport,
            ) as client:
                response = await client.post(f"/rest/v1/rpc/{name}", json=payload)
        except httpx.HTTPError as error:
            raise RepositoryUnavailableError("Supabase revalidation RPC failed") from error

        if response.is_error:
            raise RepositoryUnavailableError("Supabase revalidation RPC failed")
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as error:
            raise RepositoryUnavailableError("Supabase revalidation RPC response is invalid") from error

    @staticmethod
    def _one_record(payload: object, error_message: str) -> dict[str, object]:
        if isinstance(payload, list):
            if len(payload) != 1:
                raise RepositoryUnavailableError(error_message)
            payload = payload[0]
        if not isinstance(payload, dict):
            raise RepositoryUnavailableError(error_message)
        return payload
