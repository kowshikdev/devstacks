from datetime import datetime, timezone
from os import getenv
from xml.sax.saxutils import escape as xml_escape

from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel

from .auth import AuthenticatedUser, get_current_user, get_tenant_context
from .github_demo import (
    GitHubDemoError,
    GitHubDemoNotFoundError,
    GitHubDemoPreviewService,
    GitHubDemoSettings,
    GitHubDemoUnavailableError,
)
from .github_oauth import (
    GitHubOAuthError,
    GitHubOAuthService,
    GitHubOAuthSettings,
    GitHubOAuthUnavailableError,
    HttpGitHubOAuthClient,
)
from .github_webhook_service import (
    GitHubWebhookService,
    GitHubWebhookSubscriptionDraft,
)
from .github_webhooks import GitHubWebhookError, GitHubWebhookSettings, GitHubWebhookUnavailableError
from .rate_limit import InMemoryRateLimiter
from .repositories import (
    ProfileRepository,
    PublicProfileRepository,
    RepositoryUnavailableError,
    SupabaseAgentRunRepository,
    SupabaseClaimRepository,
    SupabaseGitHubAuthorizationRepository,
    SupabaseGitHubWebhookRepository,
    SupabaseIngestionJobRepository,
    SupabasePublicationRepository,
    SupabasePublicProfileRepository,
    SupabaseProfileRepository,
    SupabaseReviewRepository,
    SupabaseServiceSettings,
    SupabaseVerificationRepository,
)

from devstacks_domain import (
    EvidenceValidity,
    FernetTokenCipher,
    ProvenanceError,
    PublicationContext,
    PublicationRequest,
    PublicationService,
    ReviewDecisionService,
    ReviewStatus,
    TenantContext,
    TokenCipherError,
    TransitionError,
    VerificationStatus,
)


app = FastAPI(
    title="DevStacks API",
    version="0.1.0",
    description="API for the DevStacks developer evidence graph.",
)

_demo_preview_rate_limiter = InMemoryRateLimiter(max_requests=5, window_seconds=60.0)

_default_allowed_origins = "http://localhost:3000,http://127.0.0.1:3000"
_allowed_origins = [
    origin.strip()
    for origin in getenv("DEVSTACKS_ALLOWED_ORIGINS", _default_allowed_origins).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_frontend_url = getenv("DEVSTACKS_FRONTEND_URL", _allowed_origins[0] if _allowed_origins else "http://localhost:3000").rstrip("/")


def get_github_oauth_service(request: Request) -> GitHubOAuthService:
    service: GitHubOAuthService | None = getattr(
        request.app.state,
        "github_oauth_service",
        None,
    )
    if service is not None:
        return service
    try:
        oauth_settings = GitHubOAuthSettings.from_environment()
        token_cipher = FernetTokenCipher(getenv("DEVSTACKS_ENCRYPTION_KEY", ""))
        repository = SupabaseGitHubAuthorizationRepository(
            SupabaseServiceSettings.from_environment()
        )
    except (GitHubOAuthUnavailableError, RepositoryUnavailableError, TokenCipherError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub connector service is unavailable",
        ) from error
    return GitHubOAuthService(
        oauth_settings,
        token_cipher,
        repository,
        HttpGitHubOAuthClient(oauth_settings),
    )


def get_ingestion_job_repository(request: Request) -> SupabaseIngestionJobRepository:
    repository: SupabaseIngestionJobRepository | None = getattr(
        request.app.state,
        "ingestion_job_repository",
        None,
    )
    if repository is not None:
        return repository
    try:
        return SupabaseIngestionJobRepository(SupabaseServiceSettings.from_environment())
    except RepositoryUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion service is unavailable",
        ) from error


def get_github_webhook_service(request: Request) -> GitHubWebhookService:
    service: GitHubWebhookService | None = getattr(
        request.app.state,
        "github_webhook_service",
        None,
    )
    if service is not None:
        return service
    try:
        return GitHubWebhookService(
            GitHubWebhookSettings.from_environment(),
            SupabaseGitHubWebhookRepository(SupabaseServiceSettings.from_environment()),
        )
    except (GitHubWebhookUnavailableError, RepositoryUnavailableError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub webhook service is unavailable",
        ) from error


def get_github_webhook_repository(request: Request) -> SupabaseGitHubWebhookRepository:
    repository: SupabaseGitHubWebhookRepository | None = getattr(
        request.app.state,
        "github_webhook_repository",
        None,
    )
    if repository is not None:
        return repository
    try:
        return SupabaseGitHubWebhookRepository(SupabaseServiceSettings.from_environment())
    except RepositoryUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub webhook service is unavailable",
        ) from error


def get_claim_repository(request: Request) -> SupabaseClaimRepository:
    repository: SupabaseClaimRepository | None = getattr(request.app.state, "claim_repository", None)
    if repository is not None:
        return repository
    try:
        return SupabaseClaimRepository(SupabaseServiceSettings.from_environment())
    except RepositoryUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Claims service is unavailable",
        ) from error


def get_verification_repository(request: Request) -> SupabaseVerificationRepository:
    repository: SupabaseVerificationRepository | None = getattr(
        request.app.state, "verification_repository", None
    )
    if repository is not None:
        return repository
    try:
        return SupabaseVerificationRepository(SupabaseServiceSettings.from_environment())
    except RepositoryUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Verification service is unavailable",
        ) from error


def get_review_repository(request: Request) -> SupabaseReviewRepository:
    repository: SupabaseReviewRepository | None = getattr(request.app.state, "review_repository", None)
    if repository is not None:
        return repository
    try:
        return SupabaseReviewRepository(SupabaseServiceSettings.from_environment())
    except RepositoryUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Review service is unavailable",
        ) from error


def get_publication_repository(request: Request) -> SupabasePublicationRepository:
    repository: SupabasePublicationRepository | None = getattr(
        request.app.state, "publication_repository", None
    )
    if repository is not None:
        return repository
    try:
        return SupabasePublicationRepository(SupabaseServiceSettings.from_environment())
    except RepositoryUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Publication service is unavailable",
        ) from error


def get_agent_run_repository(request: Request) -> SupabaseAgentRunRepository:
    repository: SupabaseAgentRunRepository | None = getattr(
        request.app.state, "agent_run_repository", None
    )
    if repository is not None:
        return repository
    try:
        return SupabaseAgentRunRepository(SupabaseServiceSettings.from_environment())
    except RepositoryUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent run service is unavailable",
        ) from error


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/me", tags=["identity"])
async def current_user(
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, str | None]:
    """Return the authenticated subject available to tenant-aware services."""
    return {"id": user.id, "email": user.email}


@app.get("/v1/profile", tags=["profiles"])
async def own_profile(
    request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
) -> dict[str, str | bool | None]:
    """Return the profile belonging to the validated caller only."""
    repository: ProfileRepository | None = getattr(
        request.app.state,
        "profile_repository",
        None,
    )
    if repository is None:
        try:
            repository = SupabaseProfileRepository(SupabaseServiceSettings.from_environment())
        except RepositoryUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Profile service is unavailable",
            ) from error

    try:
        profile = await repository.get_own_profile(tenant)
    except RepositoryUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Profile service is unavailable",
        ) from error
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )
    return {
        "id": profile.id,
        "handle": profile.handle,
        "display_name": profile.display_name,
        "is_public": profile.is_public,
    }


class CreateProfileBody(BaseModel):
    handle: str
    display_name: str | None = None


@app.post("/v1/profile", tags=["profiles"])
async def create_profile(
    body: CreateProfileBody,
    request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
) -> dict[str, str | bool | None]:
    """Create the one profile row for a newly authenticated subject that has none yet."""
    repository: ProfileRepository | None = getattr(request.app.state, "profile_repository", None)
    if repository is None:
        try:
            repository = SupabaseProfileRepository(SupabaseServiceSettings.from_environment())
        except RepositoryUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Profile service is unavailable",
            ) from error

    try:
        profile = await repository.create_own_profile(tenant, body.handle, body.display_name)
    except RepositoryUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Profile service is unavailable",
        ) from error
    return {
        "id": profile.id,
        "handle": profile.handle,
        "display_name": profile.display_name,
        "is_public": profile.is_public,
    }


@app.get("/v1/public/profiles/{handle}", tags=["public-profiles"])
async def published_profile(
    handle: str,
    request: Request,
) -> dict[str, str | None | list[dict[str, str | None]]]:
    """Return a read-only projection of published claims for a public profile."""
    repository: PublicProfileRepository | None = getattr(
        request.app.state,
        "public_profile_repository",
        None,
    )
    if repository is None:
        try:
            repository = SupabasePublicProfileRepository(
                SupabaseServiceSettings.from_environment()
            )
        except RepositoryUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Public profile service is unavailable",
            ) from error
    try:
        profile = await repository.get_published_profile(handle)
    except RepositoryUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Public profile service is unavailable",
        ) from error
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Public profile not found",
        )
    return {
        "id": profile.id,
        "handle": profile.handle,
        "display_name": profile.display_name,
        "claims": [
            {
                "id": claim.id,
                "category": claim.category,
                "statement": claim.statement,
                "assurance_class": claim.assurance_class,
                "freshness_status": claim.freshness_status,
                "last_verified_at": claim.last_verified_at,
            }
            for claim in profile.claims
        ],
    }


def _render_badge_svg(label: str, value: str, value_color: str) -> str:
    """Render a shields.io-style flat badge SVG for embedding in READMEs."""
    char_width = 6.5
    padding = 10
    label_width = round(len(label) * char_width + padding * 2)
    value_width = round(len(value) * char_width + padding * 2)
    total_width = label_width + value_width
    label_x = label_width / 2
    value_x = label_width + value_width / 2
    label_escaped = xml_escape(label)
    value_escaped = xml_escape(value)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" role="img" aria-label="{label_escaped}: {value_escaped}">
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="{total_width}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_width}" height="20" fill="#2d2d2d"/>
    <rect x="{label_width}" width="{value_width}" height="20" fill="{value_color}"/>
    <rect width="{total_width}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="{label_x}" y="14">{label_escaped}</text>
    <text x="{value_x}" y="14">{value_escaped}</text>
  </g>
</svg>"""


@app.get("/v1/public/profiles/{handle}/badge.svg", tags=["public-profiles"])
async def public_profile_badge(handle: str, request: Request) -> Response:
    """Render an embeddable README badge showing verified claim count for a public profile."""
    repository: PublicProfileRepository | None = getattr(
        request.app.state,
        "public_profile_repository",
        None,
    )
    if repository is None:
        try:
            repository = SupabasePublicProfileRepository(
                SupabaseServiceSettings.from_environment()
            )
        except RepositoryUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Public profile service is unavailable",
            ) from error
    try:
        profile = await repository.get_published_profile(handle)
    except RepositoryUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Public profile service is unavailable",
        ) from error

    if profile is None:
        svg = _render_badge_svg("devstacks", "not found", "#9f9f9f")
    else:
        count = len(profile.claims)
        value = f"{count} verified claim{'s' if count != 1 else ''}"
        color = "#34d399" if count > 0 else "#9f9f9f"
        svg = _render_badge_svg("devstacks", value, color)

    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600, stale-while-revalidate=86400"},
    )


class DemoPreviewRequest(BaseModel):
    github_username: str


@app.post("/v1/demo/github-preview", tags=["demo"])
async def github_demo_preview(body: DemoPreviewRequest, request: Request) -> dict[str, object]:
    """Bounded, unauthenticated, non-persisted preview of a public GitHub username.

    No login, no evidence write, no agent run — lets a visitor see real
    GitHub facts about themselves before deciding to connect an account.
    """
    client_host = request.client.host if request.client else "unknown"
    if not _demo_preview_rate_limiter.allow(client_host):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many demo requests, try again shortly",
        )

    username = body.github_username.strip()
    if not username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="github_username is required")

    service: GitHubDemoPreviewService | None = getattr(
        request.app.state,
        "github_demo_preview_service",
        None,
    )
    if service is None:
        service = GitHubDemoPreviewService(GitHubDemoSettings.from_environment())

    try:
        preview = await service.preview(username)
    except GitHubDemoNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GitHub username was not found") from error
    except GitHubDemoUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub demo preview is unavailable",
        ) from error
    except GitHubDemoError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GitHub demo preview failed") from error

    return {
        "username": preview.username,
        "display_name": preview.display_name,
        "avatar_url": preview.avatar_url,
        "public_repos": preview.public_repos,
        "top_languages": list(preview.top_languages),
        "repositories": [
            {
                "name": repository.name,
                "html_url": repository.html_url,
                "description": repository.description,
                "language": repository.language,
                "stargazers_count": repository.stargazers_count,
                "pushed_at": repository.pushed_at,
            }
            for repository in preview.repositories
        ],
        "recent_commits": [
            {
                "repository": commit.repository,
                "sha": commit.sha,
                "message": commit.message,
                "html_url": commit.html_url,
                "authored_at": commit.authored_at,
            }
            for commit in preview.recent_commits
        ],
        "is_preview": True,
    }


@app.post("/v1/connectors/github/authorize", tags=["github"])
async def begin_github_authorization(
    request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
) -> dict[str, str]:
    """Create a single-use state and return the GitHub OAuth authorization URL."""
    service = get_github_oauth_service(request)
    try:
        return {"authorization_url": await service.begin(tenant)}
    except RepositoryUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub connector service is unavailable",
        ) from error


@app.get("/v1/connectors/github/callback", tags=["github"])
async def complete_github_authorization(
    request: Request,
    state: str | None = None,
    code: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Consume a GitHub OAuth callback state, bind the validated GitHub identity, and
    hand the browser back to the frontend (this endpoint is hit directly by GitHub's
    redirect, never by the frontend itself)."""
    connect_url = f"{_frontend_url}/dashboard/connect/github"

    if error:
        return RedirectResponse(f"{connect_url}?{urlencode({'error': 'denied'})}")

    service = get_github_oauth_service(request)
    try:
        connection = await service.complete(state or "", code or "")
    except GitHubOAuthError:
        return RedirectResponse(f"{connect_url}?{urlencode({'error': 'invalid'})}")
    except (GitHubOAuthUnavailableError, RepositoryUnavailableError):
        return RedirectResponse(f"{connect_url}?{urlencode({'error': 'unavailable'})}")

    return RedirectResponse(
        f"{connect_url}?{urlencode({'connected': '1', 'github_login': connection.login, 'connection_id': connection.id})}"
    )


@app.post("/v1/connectors/github/{connection_id}/sync", tags=["github"])
async def queue_github_sync(
    connection_id: str,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    tenant: TenantContext = Depends(get_tenant_context),
) -> dict[str, str]:
    """Queue an idempotent, worker-executed GitHub evidence refresh."""
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required",
        )
    repository = get_ingestion_job_repository(request)
    try:
        run_id = await repository.enqueue_github(
            tenant.profile_id,
            connection_id,
            idempotency_key,
        )
    except (RepositoryUnavailableError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion service is unavailable",
        ) from error
    return {"run_id": run_id}


@app.post("/v1/webhooks/github", status_code=status.HTTP_202_ACCEPTED, tags=["github"])
async def receive_github_webhook(request: Request) -> dict[str, str | bool | None]:
    """Verify and atomically process a GitHub repository webhook delivery."""
    service = get_github_webhook_service(request)
    try:
        result = await service.handle(
            await request.body(),
            request.headers.get("x-hub-signature-256"),
            request.headers.get("x-github-delivery"),
            request.headers.get("x-github-event"),
            request.headers.get("x-github-hook-id"),
        )
    except GitHubWebhookError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="GitHub webhook signature or delivery is invalid",
        ) from error
    except RepositoryUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub webhook service is unavailable",
        ) from error
    if result is None:
        return {"accepted": True, "queued_run_id": None, "duplicate": False}
    return {
        "accepted": True,
        "queued_run_id": result.ingestion_run_id,
        "duplicate": result.is_duplicate,
    }


@app.post("/v1/connectors/github/{connection_id}/webhooks", tags=["github"])
async def register_github_webhook(
    connection_id: str,
    github_repository_id: int,
    github_hook_id: int,
    request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
) -> dict[str, str | int]:
    """Register a manually-created repository webhook to the caller's connection."""
    try:
        draft = GitHubWebhookSubscriptionDraft(github_repository_id, github_hook_id)
        subscription = await get_github_webhook_repository(request).register_subscription(
            tenant,
            connection_id,
            draft,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub webhook identifiers are invalid",
        ) from error
    except RepositoryUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub webhook service is unavailable",
        ) from error
    return {
        "id": subscription.id,
        "connection_id": subscription.connection_id,
        "github_repository_id": subscription.github_repository_id,
        "github_hook_id": subscription.github_hook_id,
    }


@app.get("/v1/claims", tags=["claims"])
async def list_claims(
    request: Request,
    review: str | None = None,
    tenant: TenantContext = Depends(get_tenant_context),
) -> dict[str, list[dict[str, object]]]:
    """Return claim revisions for the review dashboard. Only review=pending is supported."""
    if review != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only review=pending is supported",
        )
    repository = get_claim_repository(request)
    try:
        claims = await repository.list_pending(tenant.profile_id)
    except RepositoryUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Claims service is unavailable",
        ) from error
    return {"claims": list(claims)}


class ReviewDecisionBody(BaseModel):
    note: str | None = None


@app.post("/v1/claim-revisions/{claim_revision_id}/approve", tags=["claims"])
async def approve_claim_revision(
    claim_revision_id: str,
    body: ReviewDecisionBody,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
) -> dict[str, str]:
    """Ordinary audited human transition. Never agent-driven."""
    service = ReviewDecisionService(get_review_repository(request), get_claim_repository(request))
    try:
        decision_id = await service.record(
            tenant.profile_id,
            claim_revision_id,
            ReviewStatus.APPROVED,
            actor_user_id=user.id,
            note=body.note,
        )
    except TransitionError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except RepositoryUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Review service is unavailable",
        ) from error
    return {"review_decision_id": decision_id}


@app.post("/v1/claim-revisions/{claim_revision_id}/reject", tags=["claims"])
async def reject_claim_revision(
    claim_revision_id: str,
    body: ReviewDecisionBody,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
) -> dict[str, str]:
    """Ordinary audited human transition. Never agent-driven."""
    service = ReviewDecisionService(get_review_repository(request), get_claim_repository(request))
    try:
        decision_id = await service.record(
            tenant.profile_id,
            claim_revision_id,
            ReviewStatus.REJECTED,
            actor_user_id=user.id,
            note=body.note,
        )
    except TransitionError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except RepositoryUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Review service is unavailable",
        ) from error
    return {"review_decision_id": decision_id}


class EditClaimRevisionBody(BaseModel):
    claim_id: str
    category: str
    statement: str


@app.post("/v1/claim-revisions/{claim_revision_id}/edit", tags=["claims"])
async def edit_claim_revision(
    claim_revision_id: str,
    body: EditClaimRevisionBody,
    request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
) -> dict[str, str | int]:
    """Editing a claim revision never mutates it: it creates the next immutable revision."""
    service = ReviewDecisionService(get_review_repository(request), get_claim_repository(request))
    try:
        record = await service.edit(
            tenant.profile_id,
            body.claim_id,
            claim_revision_id,
            body.category,
            body.statement,
        )
    except RepositoryUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Claims service is unavailable",
        ) from error
    return {
        "claim_id": record.claim_id,
        "claim_revision_id": record.claim_revision_id,
        "revision_number": record.revision_number,
    }


@app.post("/v1/claim-revisions/{claim_revision_id}/publish", tags=["claims"])
async def publish_claim_revision(
    claim_revision_id: str,
    request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
) -> dict[str, str]:
    """Only succeeds once the claim revision is verified and approved with current evidence."""
    repository = get_publication_repository(request)
    try:
        publication_context = await repository.get_publication_context(
            tenant.profile_id,
            claim_revision_id,
        )
    except RepositoryUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Publication service is unavailable",
        ) from error

    verification_decision_id = publication_context.get("verification_decision_id")
    verification_status_value = publication_context.get("verification_status")
    review_decision_id = publication_context.get("review_decision_id")
    review_status_value = publication_context.get("review_status")
    evidence_version_ids = publication_context.get("evidence_version_ids") or []
    evidence_validity_values = publication_context.get("evidence_validity") or []
    source_artifact_ids = publication_context.get("source_artifact_ids") or []

    if not isinstance(verification_decision_id, str) or not isinstance(verification_status_value, str):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claim revision has no verification decision",
        )

    published_at = datetime.now(timezone.utc).isoformat()
    service = PublicationService(repository)
    try:
        publication_id = await service.publish(
            tenant.profile_id,
            PublicationContext(
                claim_revision_id=claim_revision_id,
                verification_decision_id=verification_decision_id,
                review_decision_id=review_decision_id if isinstance(review_decision_id, str) else None,
                request=PublicationRequest(
                    claim_revision_id=claim_revision_id,
                    verification_status=VerificationStatus(verification_status_value),
                    review_status=(
                        ReviewStatus(review_status_value)
                        if isinstance(review_status_value, str)
                        else ReviewStatus.NOT_REQUIRED
                    ),
                    evidence_version_ids=frozenset(evidence_version_ids),
                    evidence_validity=frozenset(
                        EvidenceValidity(value) for value in evidence_validity_values
                    ),
                    source_artifact_ids=frozenset(source_artifact_ids),
                ),
            ),
            published_at=published_at,
        )
    except ProvenanceError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except RepositoryUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Publication service is unavailable",
        ) from error
    return {"publication_id": publication_id}


@app.get("/v1/runs/{run_id}", tags=["runs"])
async def get_run(
    run_id: str,
    request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
) -> dict[str, object]:
    """Expose agent-run progress and outcome, scoped to the caller's tenant."""
    repository = get_agent_run_repository(request)
    try:
        run = await repository.get(tenant.profile_id, run_id)
    except RepositoryUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent run service is unavailable",
        ) from error
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run