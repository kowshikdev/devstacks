from os import getenv

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status

from .auth import AuthenticatedUser, get_current_user, get_tenant_context
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
from .repositories import (
    ProfileRepository,
    PublicProfileRepository,
    RepositoryUnavailableError,
    SupabaseGitHubAuthorizationRepository,
    SupabaseGitHubWebhookRepository,
    SupabaseIngestionJobRepository,
    SupabasePublicProfileRepository,
    SupabaseProfileRepository,
    SupabaseServiceSettings,
)

from devstacks_domain import FernetTokenCipher, TenantContext, TokenCipherError


app = FastAPI(
    title="DevStacks API",
    version="0.1.0",
    description="API for the DevStacks developer evidence graph.",
)


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
) -> dict[str, str]:
    """Consume a GitHub OAuth callback state and bind the validated GitHub identity."""
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub authorization was denied",
        )
    service = get_github_oauth_service(request)
    try:
        connection = await service.complete(state or "", code or "")
    except GitHubOAuthError as oauth_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub authorization could not be completed",
        ) from oauth_error
    except (GitHubOAuthUnavailableError, RepositoryUnavailableError) as oauth_error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub connector service is unavailable",
        ) from oauth_error
    return {
        "connection_id": connection.id,
        "source_subject_id": connection.source_subject_id,
        "github_login": connection.login,
    }


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