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
    AgentRunLease,
    CandidateClaimRevision,
    ClaimEvidenceLinkDraft,
    ClaimRevisionRecord,
    FreshnessAssessmentDraft,
    PublicationStatus,
    RevalidationRepository,
    ReviewStatus,
    VerificationStatus,
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
class PublishedEvidence:
    """One evidence version behind a published claim, safe for public display.

    Carries no observed payload and no source reference: the content hash is
    what proves the observation is fixed, without disclosing what it points at.
    """

    evidence_version_id: str
    relation: str
    source_type: str
    content_hash: str
    version_number: int
    connector_version: str
    assurance_class: str
    validity: str
    observed_at: str | None


@dataclass(frozen=True)
class PublishedClaimTrail:
    handle: str
    display_name: str | None
    claim_revision_id: str
    category: str
    statement: str
    verification_status: str
    verifier_score: float | None
    verified_at: str
    freshness_status: str | None
    published_at: str | None
    evidence: tuple[PublishedEvidence, ...]


@dataclass(frozen=True)
class PublishedProfile:
    id: str
    handle: str
    display_name: str | None
    claims: tuple[PublishedClaim, ...]


@dataclass(frozen=True)
class ConnectorRun:
    """The most recent ingestion run observed for a connection."""

    id: str
    status: str
    trigger_type: str
    created_at: str
    started_at: str | None
    completed_at: str | None
    error_summary: str | None


@dataclass(frozen=True)
class ConnectorSummary:
    """A caller-owned source connection, with no credential material."""

    id: str
    platform: str
    external_subject: str | None
    connection_status: str
    connected_at: str | None
    last_synced_at: str | None
    latest_run: ConnectorRun | None


class ConnectorRepository(Protocol):
    async def list_own_connectors(self, tenant: TenantContext) -> tuple[ConnectorSummary, ...]:
        """Return every source connection belonging to exactly one tenant."""

    async def get_own_run(self, tenant: TenantContext, run_id: str) -> ConnectorRun | None:
        """Return one ingestion run, only when the caller's tenant owns it."""


class ProfileRepository(Protocol):
    async def get_own_profile(self, tenant: TenantContext) -> ProfileSummary | None:
        """Return the profile for exactly one authenticated tenant."""

    async def create_own_profile(
        self,
        tenant: TenantContext,
        handle: str,
        display_name: str | None,
    ) -> ProfileSummary:
        """Create the one profile row for an authenticated subject that has none yet."""


@dataclass(frozen=True)
class CommunitySpace:
    id: str
    slug: str
    name: str
    description: str
    topic_categories: tuple[str, ...]
    allowed_intents: tuple[str, ...]
    thread_count: int = 0


@dataclass(frozen=True)
class CommunityAuthor:
    profile_id: str
    handle: str
    display_name: str | None
    #: Published claim categories this author holds, used to show topic-matched
    #: standing instead of a participation score.
    verified_categories: tuple[str, ...] = ()


@dataclass(frozen=True)
class CommunityPost:
    id: str
    space_slug: str
    parent_post_id: str | None
    title: str | None
    body: str
    intent: str
    visibility: str
    reply_count: int
    created_at: str
    author: CommunityAuthor


@dataclass(frozen=True)
class CommunityPostRecord:
    post_id: str
    decision_id: str


class CommunityRepository(Protocol):
    async def list_spaces(self) -> tuple[CommunitySpace, ...]:
        """Return every space open for posting."""

    async def get_space(self, slug: str) -> CommunitySpace | None:
        """Return one space by its stable slug."""

    async def list_threads(self, slug: str, limit: int) -> tuple[CommunityPost, ...]:
        """Return published threads in a space, newest first."""

    async def get_thread(self, post_id: str) -> tuple[CommunityPost, ...]:
        """Return a published thread followed by its published replies."""

    async def create_post(
        self,
        tenant: TenantContext,
        space_slug: str,
        parent_post_id: str | None,
        title: str | None,
        body: str,
        verdict: object,
    ) -> CommunityPostRecord:
        """Persist a post together with the verdict that admitted it."""


class PublicProfileRepository(Protocol):
    async def get_published_profile(self, handle: str) -> PublishedProfile | None:
        """Return a public projection containing published claims only."""

    async def get_published_claim_trail(
        self,
        handle: str,
        claim_revision_id: str,
    ) -> PublishedClaimTrail | None:
        """Return the evidence trail behind one published claim."""


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
                headers={
                    "apikey": self._settings.service_role_key,
                    "Authorization": f"Bearer {self._settings.service_role_key}",
                },
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

    async def create_own_profile(
        self,
        tenant: TenantContext,
        handle: str,
        display_name: str | None,
    ) -> ProfileSummary:
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.url,
                headers={
                    "apikey": self._settings.service_role_key,
                    "Authorization": f"Bearer {self._settings.service_role_key}",
                },
                timeout=5.0,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    "/rest/v1/rpc/create_own_profile",
                    json={
                        "p_profile_id": tenant.profile_id,
                        "p_handle": handle,
                        "p_display_name": display_name,
                    },
                )
        except httpx.HTTPError as error:
            raise RepositoryUnavailableError("Supabase profile creation failed") from error

        if response.is_error:
            raise RepositoryUnavailableError("Supabase profile creation failed")

        record = response.json()
        if isinstance(record, list):
            if len(record) != 1:
                raise RepositoryUnavailableError("Supabase profile creation response is invalid")
            record = record[0]
        if not isinstance(record, dict):
            raise RepositoryUnavailableError("Supabase profile creation response is invalid")

        profile_id = record.get("id")
        response_handle = record.get("handle")
        is_public = record.get("is_public")
        if (
            not isinstance(profile_id, str)
            or not isinstance(response_handle, str)
            or profile_id != tenant.profile_id
            or not isinstance(is_public, bool)
        ):
            raise RepositoryUnavailableError("Supabase profile creation response violates tenant scope")

        response_display_name = record.get("display_name")
        return ProfileSummary(
            id=profile_id,
            handle=response_handle,
            display_name=response_display_name if isinstance(response_display_name, str) else None,
            is_public=is_public,
        )


class SupabaseCommunityRepository:
    """Server-only reader and writer for community spaces and posts."""

    _SPACE_FIELDS = "id,slug,name,description,topic_categories,allowed_intents"
    _POST_FIELDS = (
        "id,space_id,parent_post_id,title,body,intent,visibility,reply_count,created_at,profile_id"
    )

    def __init__(
        self,
        settings: SupabaseServiceSettings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def list_spaces(self) -> tuple[CommunitySpace, ...]:
        records = await self._select(
            "community_spaces",
            {"is_archived": "eq.false", "select": self._SPACE_FIELDS, "order": "slug.asc"},
        )
        return tuple(self._space(record) for record in records)

    async def get_space(self, slug: str) -> CommunitySpace | None:
        if not slug:
            return None
        records = await self._select(
            "community_spaces",
            {"slug": f"eq.{slug}", "is_archived": "eq.false", "select": self._SPACE_FIELDS},
        )
        return self._space(records[0]) if records else None

    async def list_threads(self, slug: str, limit: int = 50) -> tuple[CommunityPost, ...]:
        space = await self.get_space(slug)
        if space is None:
            return ()
        records = await self._select(
            "community_posts",
            {
                "space_id": f"eq.{space.id}",
                "parent_post_id": "is.null",
                "visibility": "eq.published",
                "select": self._POST_FIELDS,
                "order": "created_at.desc",
                "limit": str(limit),
            },
        )
        return await self._with_authors(records, slug)

    async def get_thread(self, post_id: str) -> tuple[CommunityPost, ...]:
        if not post_id:
            return ()
        roots = await self._select(
            "community_posts",
            {
                "id": f"eq.{post_id}",
                "parent_post_id": "is.null",
                "visibility": "eq.published",
                "select": self._POST_FIELDS,
            },
        )
        if not roots:
            return ()
        replies = await self._select(
            "community_posts",
            {
                "parent_post_id": f"eq.{post_id}",
                "visibility": "eq.published",
                "select": self._POST_FIELDS,
                "order": "created_at.asc",
            },
        )
        slug = await self._slug_for_space(str(roots[0].get("space_id")))
        return await self._with_authors([*roots, *replies], slug)

    async def create_post(
        self,
        tenant: TenantContext,
        space_slug: str,
        parent_post_id: str | None,
        title: str | None,
        body: str,
        verdict: object,
    ) -> CommunityPostRecord:
        # Imported here so the domain guardrails stay a domain concern and the
        # repository layer keeps no opinion about how a verdict is reached.
        from devstacks_domain import ModerationAction, ModerationVerdict

        if not isinstance(verdict, ModerationVerdict):
            raise ValueError("a moderation verdict is required to create a post")

        visibility = {
            ModerationAction.ALLOW: "published",
            ModerationAction.ALLOW_WITH_NOTICE: "published",
            ModerationAction.HOLD_FOR_REVIEW: "held",
            ModerationAction.BLOCK: "blocked",
        }[verdict.action]

        record = await self._call_rpc(
            "create_community_post",
            {
                "p_profile_id": tenant.profile_id,
                "p_space_slug": space_slug,
                "p_parent_post_id": parent_post_id,
                "p_title": title,
                "p_body": body,
                "p_intent": str(verdict.intent),
                "p_visibility": visibility,
                "p_action": str(verdict.action),
                "p_severity": str(verdict.severity),
                "p_policy_version": verdict.policy_version,
                "p_rationale": verdict.rationale,
                "p_signals": [
                    {
                        "kind": str(signal.kind),
                        "severity": str(signal.severity),
                        "rule_id": signal.rule_id,
                        "explanation": signal.explanation,
                        "excerpt": signal.excerpt,
                    }
                    for signal in verdict.signals
                ],
            },
        )
        post_id = record.get("post_id")
        decision_id = record.get("decision_id")
        if not isinstance(post_id, str) or not isinstance(decision_id, str):
            raise RepositoryUnavailableError("Supabase community write response is incomplete")
        return CommunityPostRecord(post_id=post_id, decision_id=decision_id)

    async def _with_authors(
        self,
        records: list[dict[str, object]],
        slug: str,
    ) -> tuple[CommunityPost, ...]:
        profile_ids = {
            str(record.get("profile_id"))
            for record in records
            if isinstance(record.get("profile_id"), str)
        }
        authors = await self._authors(profile_ids)
        unknown = CommunityAuthor(profile_id="", handle="unknown", display_name=None)
        return tuple(
            self._post(record, slug, authors.get(str(record.get("profile_id")), unknown))
            for record in records
        )

    async def _authors(self, profile_ids: set[str]) -> dict[str, CommunityAuthor]:
        if not profile_ids:
            return {}
        ids = ",".join(sorted(profile_ids))
        profiles = await self._select(
            "profiles",
            {"id": f"in.({ids})", "select": "id,handle,display_name"},
        )
        # Standing in a space comes from published claims, not from a post count.
        categories: dict[str, set[str]] = {}
        claims = await self._select(
            "claims",
            {"profile_id": f"in.({ids})", "select": "profile_id,category"},
        )
        for claim in claims:
            profile_id = claim.get("profile_id")
            category = claim.get("category")
            if isinstance(profile_id, str) and isinstance(category, str):
                categories.setdefault(profile_id, set()).add(category)

        authors: dict[str, CommunityAuthor] = {}
        for record in profiles:
            profile_id = record.get("id")
            handle = record.get("handle")
            if not isinstance(profile_id, str) or not isinstance(handle, str):
                continue
            display_name = record.get("display_name")
            authors[profile_id] = CommunityAuthor(
                profile_id=profile_id,
                handle=handle,
                display_name=display_name if isinstance(display_name, str) else None,
                verified_categories=tuple(sorted(categories.get(profile_id, set()))),
            )
        return authors

    async def _slug_for_space(self, space_id: str) -> str:
        records = await self._select(
            "community_spaces", {"id": f"eq.{space_id}", "select": "slug"}
        )
        slug = records[0].get("slug") if records else None
        return slug if isinstance(slug, str) else ""

    @staticmethod
    def _space(record: dict[str, object]) -> CommunitySpace:
        space_id = record.get("id")
        slug = record.get("slug")
        name = record.get("name")
        description = record.get("description")
        if not all(isinstance(value, str) and value for value in (space_id, slug, name, description)):
            raise RepositoryUnavailableError("Supabase community space response is incomplete")
        return CommunitySpace(
            id=str(space_id),
            slug=str(slug),
            name=str(name),
            description=str(description),
            topic_categories=_string_tuple(record.get("topic_categories")),
            allowed_intents=_string_tuple(record.get("allowed_intents")),
        )

    @staticmethod
    def _post(record: dict[str, object], slug: str, author: CommunityAuthor) -> CommunityPost:
        post_id = record.get("id")
        body = record.get("body")
        created_at = record.get("created_at")
        if not all(isinstance(value, str) and value for value in (post_id, body, created_at)):
            raise RepositoryUnavailableError("Supabase community post response is incomplete")
        reply_count = record.get("reply_count")
        title = record.get("title")
        parent = record.get("parent_post_id")
        return CommunityPost(
            id=str(post_id),
            space_slug=slug,
            parent_post_id=parent if isinstance(parent, str) else None,
            title=title if isinstance(title, str) else None,
            body=str(body),
            intent=str(record.get("intent") or "unknown"),
            visibility=str(record.get("visibility") or "published"),
            reply_count=reply_count if isinstance(reply_count, int) else 0,
            created_at=str(created_at),
            author=author,
        )

    async def _select(self, table: str, params: dict[str, str]) -> list[dict[str, object]]:
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.url,
                headers=self._headers(),
                timeout=5.0,
                transport=self._transport,
            ) as client:
                response = await client.get(f"/rest/v1/{table}", params=params)
        except httpx.HTTPError as error:
            raise RepositoryUnavailableError("Supabase community query failed") from error
        return self._records(response)

    async def _call_rpc(self, name: str, payload: dict[str, object]) -> dict[str, object]:
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.url,
                headers=self._headers(),
                timeout=5.0,
                transport=self._transport,
            ) as client:
                response = await client.post(f"/rest/v1/rpc/{name}", json=payload)
        except httpx.HTTPError as error:
            raise RepositoryUnavailableError("Supabase community write failed") from error
        records = self._records(response)
        if len(records) != 1:
            raise RepositoryUnavailableError("Supabase community write response is invalid")
        return records[0]

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self._settings.service_role_key,
            "Authorization": f"Bearer {self._settings.service_role_key}",
        }

    @staticmethod
    def _records(response: httpx.Response) -> list[dict[str, object]]:
        if response.is_error:
            raise RepositoryUnavailableError("Supabase community query failed")
        try:
            records = response.json()
        except ValueError as error:
            raise RepositoryUnavailableError("Supabase community response is invalid") from error
        if isinstance(records, dict):
            records = [records]
        if not isinstance(records, list):
            raise RepositoryUnavailableError("Supabase community response is invalid")
        for record in records:
            if not isinstance(record, dict):
                raise RepositoryUnavailableError("Supabase community response is invalid")
        return records


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


class SupabaseConnectorRepository:
    """Server-only repository for connector state, scoped by a validated tenant.

    Connector rows carry no credential material — encrypted tokens live in a
    separate table that this repository never selects from — so the projection
    returned here is safe to hand to the browser.
    """

    _CONNECTION_FIELDS = (
        "id,platform,external_subject,connection_status,connected_at,last_synced_at"
    )
    _RUN_FIELDS = (
        "id,connection_id,status,trigger_type,created_at,started_at,completed_at,error_summary"
    )
    # Bounds the run query: enough history to find the newest run per connection
    # without letting a busy profile return an unbounded page.
    _RUN_LIMIT = "50"

    def __init__(
        self,
        settings: SupabaseServiceSettings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def list_own_connectors(self, tenant: TenantContext) -> tuple[ConnectorSummary, ...]:
        connections = await self._select(
            "source_connections",
            {
                "profile_id": f"eq.{tenant.profile_id}",
                "select": self._CONNECTION_FIELDS,
                "order": "created_at.desc",
            },
        )
        if not connections:
            return ()

        runs = await self._select(
            "ingestion_runs",
            {
                "profile_id": f"eq.{tenant.profile_id}",
                "select": self._RUN_FIELDS,
                "order": "created_at.desc",
                "limit": self._RUN_LIMIT,
            },
        )

        # Runs arrive newest first, so the first row seen for a connection is
        # its latest run and later rows for the same connection are history.
        latest_by_connection: dict[str, ConnectorRun] = {}
        for record in runs:
            connection_id = record.get("connection_id")
            if not isinstance(connection_id, str) or connection_id in latest_by_connection:
                continue
            latest_by_connection[connection_id] = self._run(record)

        summaries: list[ConnectorSummary] = []
        for record in connections:
            connection_id = record.get("id")
            platform = record.get("platform")
            connection_status = record.get("connection_status")
            if not isinstance(connection_id, str) or not isinstance(platform, str):
                raise RepositoryUnavailableError("Supabase connector response is incomplete")
            if not isinstance(connection_status, str):
                raise RepositoryUnavailableError("Supabase connector response is incomplete")
            summaries.append(
                ConnectorSummary(
                    id=connection_id,
                    platform=platform,
                    external_subject=self._text(record.get("external_subject")),
                    connection_status=connection_status,
                    connected_at=self._text(record.get("connected_at")),
                    last_synced_at=self._text(record.get("last_synced_at")),
                    latest_run=latest_by_connection.get(connection_id),
                )
            )
        return tuple(summaries)

    async def get_own_run(self, tenant: TenantContext, run_id: str) -> ConnectorRun | None:
        records = await self._select(
            "ingestion_runs",
            {
                "id": f"eq.{run_id}",
                # The tenant filter is applied in the query rather than after it,
                # so another tenant's run is never fetched in the first place.
                "profile_id": f"eq.{tenant.profile_id}",
                "select": self._RUN_FIELDS,
            },
        )
        if not records:
            return None
        return self._run(records[0])

    async def _select(self, table: str, params: dict[str, str]) -> list[dict[str, object]]:
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.url,
                headers={
                    "apikey": self._settings.service_role_key,
                    "Authorization": f"Bearer {self._settings.service_role_key}",
                },
                timeout=5.0,
                transport=self._transport,
            ) as client:
                response = await client.get(f"/rest/v1/{table}", params=params)
        except httpx.HTTPError as error:
            raise RepositoryUnavailableError("Supabase connector query failed") from error

        if response.is_error:
            raise RepositoryUnavailableError("Supabase connector query failed")

        records = response.json()
        if not isinstance(records, list):
            raise RepositoryUnavailableError("Supabase connector response is invalid")
        for record in records:
            if not isinstance(record, dict):
                raise RepositoryUnavailableError("Supabase connector response is invalid")
        return records

    @classmethod
    def _run(cls, record: dict[str, object]) -> ConnectorRun:
        run_id = cls._required(record, "id")
        return ConnectorRun(
            id=run_id,
            status=cls._required(record, "status"),
            trigger_type=cls._required(record, "trigger_type"),
            created_at=cls._required(record, "created_at"),
            started_at=cls._text(record.get("started_at")),
            completed_at=cls._text(record.get("completed_at")),
            error_summary=cls._text(record.get("error_summary")),
        )

    @staticmethod
    def _required(record: dict[str, object], field: str) -> str:
        value = record.get(field)
        if not isinstance(value, str) or not value:
            raise RepositoryUnavailableError("Supabase ingestion run response is incomplete")
        return value

    @staticmethod
    def _text(value: object) -> str | None:
        return value if isinstance(value, str) else None


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
                headers={
                    "apikey": self._settings.service_role_key,
                    "Authorization": f"Bearer {self._settings.service_role_key}",
                },
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

    async def get_published_claim_trail(
        self,
        handle: str,
        claim_revision_id: str,
    ) -> PublishedClaimTrail | None:
        if not handle or not claim_revision_id:
            return None
        records = await self._call_projection(
            "get_published_claim_evidence",
            {"p_handle": handle, "p_claim_revision_id": claim_revision_id},
        )
        if not records:
            return None

        first = records[0]
        if first.get("handle") != handle or first.get("claim_revision_id") != claim_revision_id:
            raise RepositoryUnavailableError("Supabase public claim response violates scope")

        category = first.get("category")
        statement = first.get("statement")
        verification_status = first.get("verification_status")
        verified_at = first.get("verified_at")
        if not all(
            isinstance(value, str) and value
            for value in (category, statement, verification_status, verified_at)
        ):
            raise RepositoryUnavailableError("Supabase public claim response is incomplete")

        display_name = first.get("display_name")
        # A claim with no linked evidence still projects one row, with the
        # evidence columns null; that is an empty trail, not a broken response.
        evidence = tuple(
            parsed
            for parsed in (self._parse_published_evidence(record) for record in records)
            if parsed is not None
        )
        return PublishedClaimTrail(
            handle=handle,
            display_name=display_name if isinstance(display_name, str) else None,
            claim_revision_id=claim_revision_id,
            category=str(category),
            statement=str(statement),
            verification_status=str(verification_status),
            verifier_score=self._score(first.get("verifier_score")),
            verified_at=str(verified_at),
            freshness_status=self._optional_text(first.get("freshness_status")),
            published_at=self._optional_text(first.get("published_at")),
            evidence=evidence,
        )

    async def _call_projection(
        self,
        name: str,
        payload: dict[str, str],
    ) -> list[dict[str, object]]:
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.url,
                headers={
                    "apikey": self._settings.service_role_key,
                    "Authorization": f"Bearer {self._settings.service_role_key}",
                },
                timeout=5.0,
                transport=self._transport,
            ) as client:
                response = await client.post(f"/rest/v1/rpc/{name}", json=payload)
        except httpx.HTTPError as error:
            raise RepositoryUnavailableError("Supabase public claim query failed") from error
        if response.is_error:
            raise RepositoryUnavailableError("Supabase public claim query failed")
        try:
            records = response.json()
        except ValueError as error:
            raise RepositoryUnavailableError("Supabase public claim response is invalid") from error
        if not isinstance(records, list):
            raise RepositoryUnavailableError("Supabase public claim response is invalid")
        for record in records:
            if not isinstance(record, dict):
                raise RepositoryUnavailableError("Supabase public claim response is invalid")
        return records

    @classmethod
    def _parse_published_evidence(cls, record: dict[str, object]) -> PublishedEvidence | None:
        evidence_version_id = record.get("evidence_version_id")
        if evidence_version_id is None:
            return None

        relation = record.get("relation")
        source_type = record.get("source_type")
        content_hash = record.get("content_hash")
        connector_version = record.get("connector_version")
        assurance_class = record.get("assurance_class")
        validity = record.get("validity")
        version_number = record.get("version_number")
        if not all(
            isinstance(value, str) and value
            for value in (
                evidence_version_id,
                relation,
                source_type,
                content_hash,
                connector_version,
                assurance_class,
                validity,
            )
        ):
            raise RepositoryUnavailableError("Supabase public claim evidence is incomplete")
        if not isinstance(version_number, int):
            raise RepositoryUnavailableError("Supabase public claim evidence is incomplete")

        return PublishedEvidence(
            evidence_version_id=str(evidence_version_id),
            relation=str(relation),
            source_type=str(source_type),
            content_hash=str(content_hash),
            version_number=version_number,
            connector_version=str(connector_version),
            assurance_class=str(assurance_class),
            validity=str(validity),
            observed_at=cls._optional_text(record.get("observed_at")),
        )

    @staticmethod
    def _optional_text(value: object) -> str | None:
        return value if isinstance(value, str) else None

    @staticmethod
    def _score(value: object) -> float | None:
        # PostgREST renders numeric as a JSON string often enough that a plain
        # isinstance check would silently drop a real score.
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None


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
                    "Authorization": f"Bearer {self._settings.service_role_key}",
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
                headers={
                    "apikey": self._settings.service_role_key,
                    "Authorization": f"Bearer {self._settings.service_role_key}",
                },
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
                headers={
                    "apikey": self._settings.service_role_key,
                    "Authorization": f"Bearer {self._settings.service_role_key}",
                },
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
                headers={
                    "apikey": self._settings.service_role_key,
                    "Authorization": f"Bearer {self._settings.service_role_key}",
                },
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
                headers={
                    "apikey": self._settings.service_role_key,
                    "Authorization": f"Bearer {self._settings.service_role_key}",
                },
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
                headers={
                    "apikey": self._settings.service_role_key,
                    "Authorization": f"Bearer {self._settings.service_role_key}",
                },
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
                headers={
                    "apikey": self._settings.service_role_key,
                    "Authorization": f"Bearer {self._settings.service_role_key}",
                },
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


class SupabaseClaimRepository:
    """Server-only adapter for claim-revision creation and evidence-link reads."""

    def __init__(
        self,
        settings: SupabaseServiceSettings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def create_claim_revision(
        self,
        profile_id: str,
        candidate: CandidateClaimRevision,
    ) -> ClaimRevisionRecord:
        payload = await self._call_rpc(
            "create_claim_revision",
            {
                "p_profile_id": profile_id,
                "p_claim_id": candidate.claim_id,
                "p_category": candidate.category,
                "p_statement": candidate.statement,
                "p_valid_from": candidate.valid_from,
                "p_valid_until": candidate.valid_until,
                "p_evidence_links": [
                    {"evidence_version_id": link.evidence_version_id, "relation": link.relation}
                    for link in candidate.evidence_links
                ],
            },
        )
        record = self._one_record(payload, "Supabase claim revision response is invalid")
        claim_id = record.get("claim_id")
        claim_revision_id = record.get("claim_revision_id")
        revision_number = record.get("revision_number")
        if (
            not isinstance(claim_id, str)
            or not isinstance(claim_revision_id, str)
            or not isinstance(revision_number, int)
        ):
            raise RepositoryUnavailableError("Supabase claim revision response is incomplete")
        return ClaimRevisionRecord(
            claim_id=claim_id,
            claim_revision_id=claim_revision_id,
            revision_number=revision_number,
        )

    async def get_evidence_links(
        self,
        profile_id: str,
        claim_revision_id: str,
    ) -> tuple[ClaimEvidenceLinkDraft, ...]:
        payload = await self._call_rpc(
            "get_claim_revision_evidence_links",
            {"p_profile_id": profile_id, "p_claim_revision_id": claim_revision_id},
        )
        if not isinstance(payload, list):
            raise RepositoryUnavailableError("Supabase evidence link response is invalid")
        links = []
        for record in payload:
            if not isinstance(record, dict):
                raise RepositoryUnavailableError("Supabase evidence link response is invalid")
            evidence_version_id = record.get("evidence_version_id")
            relation = record.get("relation")
            if not isinstance(evidence_version_id, str) or not isinstance(relation, str):
                raise RepositoryUnavailableError("Supabase evidence link response is incomplete")
            links.append(ClaimEvidenceLinkDraft(evidence_version_id=evidence_version_id, relation=relation))
        return tuple(links)

    async def get_evidence_version(
        self,
        profile_id: str,
        evidence_version_id: str,
    ) -> dict[str, object] | None:
        payload = await self._call_rpc(
            "get_evidence_version",
            {"p_profile_id": profile_id, "p_evidence_version_id": evidence_version_id},
        )
        if payload == [] or payload is None:
            return None
        return self._one_record(payload, "Supabase evidence version response is invalid")

    async def list_pending(self, profile_id: str) -> tuple[dict[str, object], ...]:
        payload = await self._call_rpc(
            "list_pending_claim_revisions",
            {"p_profile_id": profile_id},
        )
        if not isinstance(payload, list):
            raise RepositoryUnavailableError("Supabase pending claims response is invalid")
        for record in payload:
            if not isinstance(record, dict):
                raise RepositoryUnavailableError("Supabase pending claims response is invalid")
        return tuple(payload)

    async def _call_rpc(self, name: str, payload: dict[str, object]) -> object:
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.url,
                headers={
                    "apikey": self._settings.service_role_key,
                    "Authorization": f"Bearer {self._settings.service_role_key}",
                },
                timeout=5.0,
                transport=self._transport,
            ) as client:
                response = await client.post(f"/rest/v1/rpc/{name}", json=payload)
        except httpx.HTTPError as error:
            raise RepositoryUnavailableError("Supabase claims RPC failed") from error
        if response.is_error:
            raise RepositoryUnavailableError("Supabase claims RPC failed")
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as error:
            raise RepositoryUnavailableError("Supabase claims RPC response is invalid") from error

    @staticmethod
    def _one_record(payload: object, error_message: str) -> dict[str, object]:
        if isinstance(payload, list):
            if len(payload) != 1:
                raise RepositoryUnavailableError(error_message)
            payload = payload[0]
        if not isinstance(payload, dict):
            raise RepositoryUnavailableError(error_message)
        return payload


class SupabaseVerificationRepository:
    """Server-only adapter for verification-decision reads and appends."""

    def __init__(
        self,
        settings: SupabaseServiceSettings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def get_current_verification_status(
        self,
        profile_id: str,
        claim_revision_id: str,
    ) -> VerificationStatus:
        payload = await self._call_rpc(
            "get_latest_verification_status",
            {"p_profile_id": profile_id, "p_claim_revision_id": claim_revision_id},
        )
        status = self._scalar(payload)
        if status is None:
            return VerificationStatus.UNVERIFIED
        return VerificationStatus(status)

    async def record_verification_decision(
        self,
        profile_id: str,
        claim_revision_id: str,
        status: VerificationStatus,
        verifier_score: float | None,
        agent_run_id: str | None,
        rationale: str | None,
    ) -> str:
        payload = await self._call_rpc(
            "record_verification_decision",
            {
                "p_profile_id": profile_id,
                "p_claim_revision_id": claim_revision_id,
                "p_status": status.value,
                "p_verifier_score": verifier_score,
                "p_agent_run_id": agent_run_id,
                "p_rationale": rationale,
            },
        )
        record = self._one_record(payload, "Supabase verification decision response is invalid")
        decision_id = record.get("id")
        if not isinstance(decision_id, str):
            raise RepositoryUnavailableError("Supabase verification decision response is incomplete")
        return decision_id

    async def _call_rpc(self, name: str, payload: dict[str, object]) -> object:
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.url,
                headers={
                    "apikey": self._settings.service_role_key,
                    "Authorization": f"Bearer {self._settings.service_role_key}",
                },
                timeout=5.0,
                transport=self._transport,
            ) as client:
                response = await client.post(f"/rest/v1/rpc/{name}", json=payload)
        except httpx.HTTPError as error:
            raise RepositoryUnavailableError("Supabase verification RPC failed") from error
        if response.is_error:
            raise RepositoryUnavailableError("Supabase verification RPC failed")
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as error:
            raise RepositoryUnavailableError("Supabase verification RPC response is invalid") from error

    @staticmethod
    def _scalar(payload: object) -> object:
        if isinstance(payload, list):
            if len(payload) == 0:
                return None
            if len(payload) != 1:
                raise RepositoryUnavailableError("Supabase verification status response is invalid")
            return payload[0]
        return payload

    @staticmethod
    def _one_record(payload: object, error_message: str) -> dict[str, object]:
        if isinstance(payload, list):
            if len(payload) != 1:
                raise RepositoryUnavailableError(error_message)
            payload = payload[0]
        if not isinstance(payload, dict):
            raise RepositoryUnavailableError(error_message)
        return payload


class SupabaseReviewRepository:
    """Server-only adapter for review-decision reads and appends."""

    def __init__(
        self,
        settings: SupabaseServiceSettings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def get_current_review_status(
        self,
        profile_id: str,
        claim_revision_id: str,
    ) -> ReviewStatus:
        payload = await self._call_rpc(
            "get_latest_review_status",
            {"p_profile_id": profile_id, "p_claim_revision_id": claim_revision_id},
        )
        status = self._scalar(payload)
        if status is None:
            return ReviewStatus.PENDING
        return ReviewStatus(status)

    async def record_review_decision(
        self,
        profile_id: str,
        claim_revision_id: str,
        status: ReviewStatus,
        actor_user_id: str,
        note: str | None,
    ) -> str:
        payload = await self._call_rpc(
            "record_review_decision",
            {
                "p_profile_id": profile_id,
                "p_claim_revision_id": claim_revision_id,
                "p_status": status.value,
                "p_actor_user_id": actor_user_id,
                "p_note": note,
            },
        )
        record = self._one_record(payload, "Supabase review decision response is invalid")
        decision_id = record.get("id")
        if not isinstance(decision_id, str):
            raise RepositoryUnavailableError("Supabase review decision response is incomplete")
        return decision_id

    async def _call_rpc(self, name: str, payload: dict[str, object]) -> object:
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.url,
                headers={
                    "apikey": self._settings.service_role_key,
                    "Authorization": f"Bearer {self._settings.service_role_key}",
                },
                timeout=5.0,
                transport=self._transport,
            ) as client:
                response = await client.post(f"/rest/v1/rpc/{name}", json=payload)
        except httpx.HTTPError as error:
            raise RepositoryUnavailableError("Supabase review RPC failed") from error
        if response.is_error:
            raise RepositoryUnavailableError("Supabase review RPC failed")
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as error:
            raise RepositoryUnavailableError("Supabase review RPC response is invalid") from error

    @staticmethod
    def _scalar(payload: object) -> object:
        if isinstance(payload, list):
            if len(payload) == 0:
                return None
            if len(payload) != 1:
                raise RepositoryUnavailableError("Supabase review status response is invalid")
            return payload[0]
        return payload

    @staticmethod
    def _one_record(payload: object, error_message: str) -> dict[str, object]:
        if isinstance(payload, list):
            if len(payload) != 1:
                raise RepositoryUnavailableError(error_message)
            payload = payload[0]
        if not isinstance(payload, dict):
            raise RepositoryUnavailableError(error_message)
        return payload


class SupabasePublicationRepository:
    """Server-only adapter for provenance-guarded publication writes."""

    def __init__(
        self,
        settings: SupabaseServiceSettings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def record_publication(
        self,
        profile_id: str,
        claim_revision_id: str,
        verification_decision_id: str,
        review_decision_id: str | None,
        policy_version_id: str | None,
        status: PublicationStatus,
        published_at: str | None,
        withdrawn_at: str | None,
    ) -> str:
        payload = await self._call_rpc(
            "record_publication",
            {
                "p_profile_id": profile_id,
                "p_claim_revision_id": claim_revision_id,
                "p_verification_decision_id": verification_decision_id,
                "p_review_decision_id": review_decision_id,
                "p_policy_version_id": policy_version_id,
                "p_status": status.value,
                "p_published_at": published_at,
                "p_withdrawn_at": withdrawn_at,
            },
        )
        record = self._one_record(payload, "Supabase publication response is invalid")
        publication_id = record.get("id")
        if not isinstance(publication_id, str):
            raise RepositoryUnavailableError("Supabase publication response is incomplete")
        return publication_id

    async def get_publication_context(
        self,
        profile_id: str,
        claim_revision_id: str,
    ) -> dict[str, object]:
        payload = await self._call_rpc(
            "get_claim_revision_publication_context",
            {"p_profile_id": profile_id, "p_claim_revision_id": claim_revision_id},
        )
        return self._one_record(payload, "Supabase publication context response is invalid")

    async def _call_rpc(self, name: str, payload: dict[str, object]) -> object:
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.url,
                headers={
                    "apikey": self._settings.service_role_key,
                    "Authorization": f"Bearer {self._settings.service_role_key}",
                },
                timeout=5.0,
                transport=self._transport,
            ) as client:
                response = await client.post(f"/rest/v1/rpc/{name}", json=payload)
        except httpx.HTTPError as error:
            raise RepositoryUnavailableError("Supabase publication RPC failed") from error
        if response.is_error:
            raise RepositoryUnavailableError("Supabase publication RPC failed")
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as error:
            raise RepositoryUnavailableError("Supabase publication RPC response is invalid") from error

    @staticmethod
    def _one_record(payload: object, error_message: str) -> dict[str, object]:
        if isinstance(payload, list):
            if len(payload) != 1:
                raise RepositoryUnavailableError(error_message)
            payload = payload[0]
        if not isinstance(payload, dict):
            raise RepositoryUnavailableError(error_message)
        return payload


class SupabaseAgentRunRepository:
    """Server-only adapter for lease-based agent-run queueing and completion."""

    def __init__(
        self,
        settings: SupabaseServiceSettings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def enqueue(
        self,
        profile_id: str,
        source_artifact_id: str,
        evidence_version_id: str,
        idempotency_key: str,
    ) -> str:
        if not idempotency_key.strip():
            raise ValueError("agent run idempotency key is required")
        payload = await self._call_rpc(
            "enqueue_claim_agent_run",
            {
                "p_profile_id": profile_id,
                "p_source_artifact_id": source_artifact_id,
                "p_evidence_version_id": evidence_version_id,
                "p_idempotency_key": idempotency_key,
            },
        )
        record = self._one_record(payload, "Supabase agent run queue response is invalid")
        run_id = record.get("id")
        if not isinstance(run_id, str):
            raise RepositoryUnavailableError("Supabase agent run queue response is incomplete")
        return run_id

    async def claim(self, worker_id: str, lease_seconds: int = 300) -> AgentRunLease | None:
        if not worker_id.strip():
            raise ValueError("worker id is required")
        if not 1 <= lease_seconds <= 3600:
            raise ValueError("lease seconds must be between 1 and 3600")
        payload = await self._call_rpc(
            "claim_agent_run",
            {"p_worker_id": worker_id, "p_lease_seconds": lease_seconds},
        )
        if payload is None:
            return None
        return self._parse_lease(payload, worker_id)

    async def complete(
        self,
        lease: AgentRunLease,
        status: str,
        error_summary: str | None = None,
    ) -> None:
        if status not in {"succeeded", "failed", "interrupted"}:
            raise ValueError("agent run completion status must be terminal")
        payload = await self._call_rpc(
            "complete_agent_run",
            {
                "p_run_id": lease.id,
                "p_worker_id": lease.lease_owner,
                "p_status": status,
                "p_error_summary": error_summary,
            },
        )
        if not isinstance(payload, dict) or payload.get("id") != lease.id:
            raise RepositoryUnavailableError("Supabase agent run completion response is invalid")

    async def get(self, profile_id: str, run_id: str) -> dict[str, object] | None:
        payload = await self._call_rpc(
            "get_agent_run",
            {"p_profile_id": profile_id, "p_run_id": run_id},
        )
        if payload == [] or payload is None:
            return None
        return self._one_record(payload, "Supabase agent run response is invalid")

    async def _call_rpc(self, name: str, payload: dict[str, object]) -> object:
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.url,
                headers={
                    "apikey": self._settings.service_role_key,
                    "Authorization": f"Bearer {self._settings.service_role_key}",
                },
                timeout=5.0,
                transport=self._transport,
            ) as client:
                response = await client.post(f"/rest/v1/rpc/{name}", json=payload)
        except httpx.HTTPError as error:
            raise RepositoryUnavailableError("Supabase agent run RPC failed") from error
        if response.is_error:
            raise RepositoryUnavailableError("Supabase agent run RPC failed")
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as error:
            raise RepositoryUnavailableError("Supabase agent run RPC response is invalid") from error

    @staticmethod
    def _parse_lease(payload: object, worker_id: str) -> AgentRunLease:
        if isinstance(payload, list):
            if len(payload) != 1:
                raise RepositoryUnavailableError("Supabase agent run lease response is invalid")
            payload = payload[0]
        if not isinstance(payload, dict):
            raise RepositoryUnavailableError("Supabase agent run lease response is invalid")

        run_id = payload.get("id")
        profile_id = payload.get("profile_id")
        source_artifact_id = payload.get("source_artifact_id")
        evidence_version_id = payload.get("evidence_version_id")
        attempt_count = payload.get("attempt_count")
        lease_owner = payload.get("lease_owner")
        lease_expires_at = payload.get("lease_expires_at")
        if (
            not isinstance(run_id, str)
            or not isinstance(profile_id, str)
            or (source_artifact_id is not None and not isinstance(source_artifact_id, str))
            or (evidence_version_id is not None and not isinstance(evidence_version_id, str))
            or not isinstance(attempt_count, int)
            or attempt_count < 1
            or lease_owner != worker_id
            or not isinstance(lease_expires_at, str)
        ):
            raise RepositoryUnavailableError("Supabase agent run lease response violates worker scope")
        return AgentRunLease(
            id=run_id,
            profile_id=profile_id,
            source_artifact_id=source_artifact_id,
            evidence_version_id=evidence_version_id,
            attempt_count=attempt_count,
            lease_owner=lease_owner,
            lease_expires_at=lease_expires_at,
        )

    @staticmethod
    def _one_record(payload: object, error_message: str) -> dict[str, object]:
        if isinstance(payload, list):
            if len(payload) != 1:
                raise RepositoryUnavailableError(error_message)
            payload = payload[0]
        if not isinstance(payload, dict):
            raise RepositoryUnavailableError(error_message)
        return payload
