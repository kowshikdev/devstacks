from dataclasses import dataclass
from os import getenv

import httpx


class GitHubDemoError(ValueError):
    """Raised when GitHub returns an invalid demo-preview observation."""


class GitHubDemoNotFoundError(ValueError):
    """Raised when the requested GitHub username has no public profile."""


class GitHubDemoUnavailableError(RuntimeError):
    """Raised when GitHub cannot serve a demo-preview request."""


@dataclass(frozen=True)
class GitHubDemoRepository:
    name: str
    html_url: str
    description: str | None
    language: str | None
    stargazers_count: int
    pushed_at: str | None


@dataclass(frozen=True)
class GitHubDemoCommit:
    repository: str
    sha: str
    message: str
    html_url: str
    authored_at: str | None


@dataclass(frozen=True)
class GitHubDemoPreview:
    username: str
    display_name: str | None
    avatar_url: str | None
    public_repos: int
    repositories: tuple[GitHubDemoRepository, ...]
    recent_commits: tuple[GitHubDemoCommit, ...]
    top_languages: tuple[str, ...]


@dataclass(frozen=True)
class GitHubDemoSettings:
    client_id: str | None
    client_secret: str | None

    @classmethod
    def from_environment(cls) -> "GitHubDemoSettings":
        return cls(
            client_id=getenv("GITHUB_OAUTH_CLIENT_ID") or None,
            client_secret=getenv("GITHUB_OAUTH_CLIENT_SECRET") or None,
        )


class GitHubDemoPreviewService:
    """Bounded, unauthenticated preview of a public GitHub username's evidence.

    Never persists anything and never runs the claim-extraction agent — this
    exists purely to let an anonymous visitor see real GitHub facts about
    themselves before deciding to connect an account. Uses the app's own
    OAuth client credentials as Basic auth (not a user token) only to raise
    GitHub's unauthenticated rate limit; no scopes or user consent involved.
    """

    def __init__(
        self,
        settings: GitHubDemoSettings,
        *,
        max_repositories: int = 5,
        max_commits_per_repository: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not 1 <= max_repositories <= 20:
            raise ValueError("GitHub demo repository limit must be between 1 and 20")
        if not 1 <= max_commits_per_repository <= 20:
            raise ValueError("GitHub demo commit limit must be between 1 and 20")
        self._settings = settings
        self._max_repositories = max_repositories
        self._max_commits_per_repository = max_commits_per_repository
        self._transport = transport

    async def preview(self, username: str) -> GitHubDemoPreview:
        username = username.strip()
        if not username:
            raise GitHubDemoError("GitHub username is required")

        async with httpx.AsyncClient(
            base_url="https://api.github.com",
            timeout=15.0,
            transport=self._transport,
            auth=self._basic_auth(),
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        ) as client:
            user = await self._get_json(client, f"/users/{username}", expect_dict=True)
            repositories_payload = await self._get_json(
                client,
                f"/users/{username}/repos",
                params={"sort": "pushed", "direction": "desc", "per_page": self._max_repositories},
                expect_dict=False,
            )

            repositories: list[GitHubDemoRepository] = []
            commits: list[GitHubDemoCommit] = []
            language_counts: dict[str, int] = {}

            for repository in repositories_payload[: self._max_repositories]:
                if not isinstance(repository, dict):
                    continue
                name = repository.get("full_name")
                if not isinstance(name, str) or not name:
                    continue
                language = repository.get("language")
                language = language if isinstance(language, str) else None
                if language:
                    language_counts[language] = language_counts.get(language, 0) + 1

                repositories.append(
                    GitHubDemoRepository(
                        name=name,
                        html_url=self._required_string(repository, "html_url"),
                        description=self._optional_string(repository, "description"),
                        language=language,
                        stargazers_count=self._optional_int(repository, "stargazers_count") or 0,
                        pushed_at=self._optional_string(repository, "pushed_at"),
                    )
                )

                repository_commits = await self._get_json(
                    client,
                    f"/repos/{name}/commits",
                    params={"per_page": self._max_commits_per_repository},
                    expect_dict=False,
                    optional=True,
                )
                for commit in repository_commits[: self._max_commits_per_repository]:
                    if not isinstance(commit, dict):
                        continue
                    commit_data = commit.get("commit")
                    if not isinstance(commit_data, dict):
                        continue
                    sha = commit.get("sha")
                    message = commit_data.get("message")
                    if not isinstance(sha, str) or not isinstance(message, str):
                        continue
                    author_data = commit_data.get("author")
                    authored_at = (
                        author_data.get("date")
                        if isinstance(author_data, dict) and isinstance(author_data.get("date"), str)
                        else None
                    )
                    commits.append(
                        GitHubDemoCommit(
                            repository=name,
                            sha=sha[:12],
                            message=message.splitlines()[0][:140],
                            html_url=self._required_string(commit, "html_url"),
                            authored_at=authored_at,
                        )
                    )

            top_languages = tuple(
                sorted(language_counts, key=lambda language: language_counts[language], reverse=True)[:5]
            )

            return GitHubDemoPreview(
                username=self._required_string(user, "login"),
                display_name=self._optional_string(user, "name"),
                avatar_url=self._optional_string(user, "avatar_url"),
                public_repos=self._optional_int(user, "public_repos") or 0,
                repositories=tuple(repositories),
                recent_commits=tuple(commits),
                top_languages=top_languages,
            )

    def _basic_auth(self) -> httpx.Auth | None:
        if not self._settings.client_id or not self._settings.client_secret:
            return None
        return httpx.BasicAuth(self._settings.client_id, self._settings.client_secret)

    async def _get_json(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        *,
        expect_dict: bool,
        params: dict[str, object] | None = None,
        optional: bool = False,
    ):
        try:
            response = await client.get(endpoint, params=params or {})
        except httpx.HTTPError as error:
            raise GitHubDemoUnavailableError("GitHub demo request failed") from error

        if response.status_code == 404:
            if optional:
                return [] if not expect_dict else {}
            raise GitHubDemoNotFoundError("GitHub username was not found")
        if response.status_code in {401, 403, 429} or response.status_code >= 500:
            raise GitHubDemoUnavailableError("GitHub demo request is unavailable")
        if response.is_error:
            raise GitHubDemoError("GitHub demo request was rejected")

        try:
            payload = response.json()
        except ValueError as error:
            raise GitHubDemoError("GitHub demo response is invalid") from error

        if expect_dict:
            if not isinstance(payload, dict):
                raise GitHubDemoError("GitHub demo response must be an object")
            return payload
        if not isinstance(payload, list):
            raise GitHubDemoError("GitHub demo response must be a list")
        return payload

    @staticmethod
    def _required_string(payload: dict[str, object], name: str) -> str:
        value = payload.get(name)
        if not isinstance(value, str) or not value:
            raise GitHubDemoError(f"GitHub field {name} is invalid")
        return value

    @staticmethod
    def _optional_string(payload: dict[str, object], name: str) -> str | None:
        value = payload.get(name)
        if value is None:
            return None
        if not isinstance(value, str):
            raise GitHubDemoError(f"GitHub field {name} is invalid")
        return value

    @staticmethod
    def _optional_int(payload: dict[str, object], name: str) -> int | None:
        value = payload.get(name)
        if value is None:
            return None
        if not isinstance(value, int) or isinstance(value, bool):
            raise GitHubDemoError(f"GitHub field {name} is invalid")
        return value
