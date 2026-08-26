import asyncio

import httpx
import pytest

from devstacks_api.github_ingestion import (
    GitHubCollectionOutcome,
    GitHubEvidenceCollector,
    GitHubIngestionError,
)


def repository() -> dict[str, object]:
    return {
        "id": 101,
        "full_name": "octocat/hello-world",
        "owner": {"login": "octocat"},
        "name": "hello-world",
        "html_url": "https://github.com/octocat/hello-world",
        "default_branch": "main",
        "fork": False,
        "private": False,
        "pushed_at": "2026-08-26T00:00:00Z",
        "updated_at": "2026-08-26T00:00:00Z",
    }


def commit() -> dict[str, object]:
    return {
        "sha": "abc123",
        "html_url": "https://github.com/octocat/hello-world/commit/abc123",
        "commit": {
            "message": "Add deterministic ingestion",
            "author": {"name": "Octocat", "email": "octocat@example.com", "date": "2026-08-25T00:00:00Z"},
        },
        "author": {"login": "octocat"},
    }


def pull_request() -> dict[str, object]:
    return {
        "number": 7,
        "html_url": "https://github.com/octocat/hello-world/pull/7",
        "title": "Add evidence graph",
        "state": "closed",
        "created_at": "2026-08-20T00:00:00Z",
        "updated_at": "2026-08-25T00:00:00Z",
        "merged_at": "2026-08-25T01:00:00Z",
        "user": {"login": "octocat"},
        "base": {"ref": "main"},
        "head": {"ref": "feature/evidence"},
    }


def release() -> dict[str, object]:
    return {
        "id": 88,
        "html_url": "https://github.com/octocat/hello-world/releases/tag/v1.0.0",
        "tag_name": "v1.0.0",
        "name": "First release",
        "draft": False,
        "prerelease": False,
        "published_at": "2026-08-26T00:00:00Z",
        "author": {"login": "octocat"},
    }


def test_collector_normalizes_all_github_evidence_types():
    responses = {
        "/user/repos": [repository()],
        "/repos/octocat/hello-world/commits": [commit()],
        "/repos/octocat/hello-world/pulls": [pull_request()],
        "/repos/octocat/hello-world/releases": [release()],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer access-token"
        assert request.url.params["per_page"] == "100"
        return httpx.Response(200, json=responses[request.url.path])

    collection = asyncio.run(
        GitHubEvidenceCollector("access-token", transport=httpx.MockTransport(handler)).collect()
    )

    assert collection.outcome is GitHubCollectionOutcome.SUCCEEDED
    assert [artifact.source_ref for artifact in collection.artifacts] == [
        "github:repository:101",
        "github:commit:101:abc123",
        "github:pull_request:101:7",
        "github:release:101:88",
    ]
    assert collection.artifacts[1].payload["github_author_login"] == "octocat"


def test_collector_reports_partial_when_page_limit_is_reached():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user/repos":
            return httpx.Response(
                200,
                json=[repository()],
                headers={"Link": '<https://api.github.com/user/repos?page=2>; rel="next"'},
            )
        return httpx.Response(200, json=[])

    collection = asyncio.run(
        GitHubEvidenceCollector(
            "access-token",
            max_pages=1,
            transport=httpx.MockTransport(handler),
        ).collect()
    )

    assert collection.outcome is GitHubCollectionOutcome.PARTIAL


def test_collector_rejects_invalid_provider_records():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": 101}])

    with pytest.raises(GitHubIngestionError, match="full_name"):
        asyncio.run(
            GitHubEvidenceCollector(
                "access-token",
                transport=httpx.MockTransport(handler),
            ).collect()
        )