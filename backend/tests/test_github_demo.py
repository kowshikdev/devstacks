import asyncio

import httpx
import pytest

from devstacks_api.github_demo import (
    GitHubDemoNotFoundError,
    GitHubDemoPreviewService,
    GitHubDemoSettings,
    GitHubDemoUnavailableError,
)


def user() -> dict[str, object]:
    return {
        "login": "octocat",
        "name": "Octo Cat",
        "avatar_url": "https://github.com/images/octocat.png",
        "public_repos": 2,
    }


def repository(language: str | None = "Python") -> dict[str, object]:
    return {
        "full_name": "octocat/hello-world",
        "html_url": "https://github.com/octocat/hello-world",
        "description": "A demo repository",
        "language": language,
        "stargazers_count": 5,
        "pushed_at": "2026-08-26T00:00:00Z",
    }


def commit() -> dict[str, object]:
    return {
        "sha": "abc123def456",
        "html_url": "https://github.com/octocat/hello-world/commit/abc123def456",
        "commit": {
            "message": "Add deterministic ingestion\n\nLonger body here.",
            "author": {"date": "2026-08-25T00:00:00Z"},
        },
    }


def test_preview_normalizes_public_repositories_and_commits():
    responses = {
        "/users/octocat": user(),
        "/users/octocat/repos": [repository()],
        "/repos/octocat/hello-world/commits": [commit()],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers or request.headers["authorization"].startswith("Basic")
        return httpx.Response(200, json=responses[request.url.path])

    settings = GitHubDemoSettings(client_id="client-id", client_secret="client-secret")
    preview = asyncio.run(
        GitHubDemoPreviewService(settings, transport=httpx.MockTransport(handler)).preview("octocat")
    )

    assert preview.username == "octocat"
    assert preview.display_name == "Octo Cat"
    assert preview.public_repos == 2
    assert [repository.name for repository in preview.repositories] == ["octocat/hello-world"]
    assert preview.top_languages == ("Python",)
    assert len(preview.recent_commits) == 1
    assert preview.recent_commits[0].sha == "abc123def456"[:12]
    assert preview.recent_commits[0].message == "Add deterministic ingestion"


def test_preview_uses_basic_auth_with_client_credentials():
    seen_auth_headers: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_auth_headers.append(request.headers.get("authorization"))
        if request.url.path == "/users/octocat":
            return httpx.Response(200, json=user())
        return httpx.Response(200, json=[])

    settings = GitHubDemoSettings(client_id="client-id", client_secret="client-secret")
    asyncio.run(
        GitHubDemoPreviewService(settings, transport=httpx.MockTransport(handler)).preview("octocat")
    )

    assert all(header is not None and header.startswith("Basic ") for header in seen_auth_headers)


def test_preview_raises_not_found_for_a_missing_username():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    settings = GitHubDemoSettings(client_id=None, client_secret=None)
    with pytest.raises(GitHubDemoNotFoundError):
        asyncio.run(
            GitHubDemoPreviewService(settings, transport=httpx.MockTransport(handler)).preview("ghost")
        )


def test_preview_raises_unavailable_when_github_rate_limits_the_request():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"message": "rate limited"})

    settings = GitHubDemoSettings(client_id=None, client_secret=None)
    with pytest.raises(GitHubDemoUnavailableError):
        asyncio.run(
            GitHubDemoPreviewService(settings, transport=httpx.MockTransport(handler)).preview("octocat")
        )


def test_preview_tolerates_a_repository_with_no_commits_available():
    responses = {
        "/users/octocat": user(),
        "/users/octocat/repos": [repository(language=None)],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/octocat/hello-world/commits":
            return httpx.Response(404, json={"message": "Not Found"})
        return httpx.Response(200, json=responses[request.url.path])

    settings = GitHubDemoSettings(client_id=None, client_secret=None)
    preview = asyncio.run(
        GitHubDemoPreviewService(settings, transport=httpx.MockTransport(handler)).preview("octocat")
    )

    assert preview.recent_commits == ()
    assert preview.top_languages == ()
