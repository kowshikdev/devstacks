from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx


class GitHubIngestionError(ValueError):
    """Raised when GitHub returns an invalid provider observation."""


class GitHubIngestionUnavailableError(RuntimeError):
    """Raised when GitHub cannot provide an observation."""


class GitHubCollectionOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"


@dataclass(frozen=True)
class GitHubArtifact:
    source_type: str
    source_ref: str
    payload: dict[str, object]
    observed_at: str | None


@dataclass(frozen=True)
class GitHubCollection:
    artifacts: tuple[GitHubArtifact, ...]
    outcome: GitHubCollectionOutcome


class GitHubEvidenceCollector:
    """Bounded GitHub REST collector that produces deterministic provider observations."""

    def __init__(
        self,
        access_token: str,
        *,
        max_pages: int = 10,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not access_token:
            raise ValueError("GitHub access token is required")
        if not 1 <= max_pages <= 100:
            raise ValueError("GitHub collection page limit must be between 1 and 100")
        self._access_token = access_token
        self._max_pages = max_pages
        self._transport = transport

    async def collect(self) -> GitHubCollection:
        repositories, repositories_partial = await self._list("/user/repos")
        artifacts = [self._repository_artifact(repository) for repository in repositories]
        partial = repositories_partial
        for repository in repositories:
            repository_id = self._required_int(repository, "id")
            full_name = self._required_string(repository, "full_name")
            owner, name = self._repository_path(full_name)
            for endpoint, normalizer in (
                (f"/repos/{owner}/{name}/commits", self._commit_artifact),
                (f"/repos/{owner}/{name}/pulls", self._pull_request_artifact),
                (f"/repos/{owner}/{name}/releases", self._release_artifact),
            ):
                records, endpoint_partial = await self._list(endpoint)
                artifacts.extend(normalizer(record, repository_id) for record in records)
                partial = partial or endpoint_partial
        return GitHubCollection(
            artifacts=tuple(artifacts),
            outcome=(GitHubCollectionOutcome.PARTIAL if partial else GitHubCollectionOutcome.SUCCEEDED),
        )

    async def _list(self, endpoint: str) -> tuple[list[dict[str, object]], bool]:
        records: list[dict[str, object]] = []
        page = 1
        while page <= self._max_pages:
            response = await self._get(endpoint, params=self._list_params(endpoint, page))
            payload = self._json_list(response)
            records.extend(payload)
            next_page = self._next_page(response)
            if next_page is None:
                return records, False
            if next_page <= page:
                raise GitHubIngestionError("GitHub pagination is invalid")
            page = next_page
        return records, True

    async def _get(self, endpoint: str, params: dict[str, object]) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                base_url="https://api.github.com",
                timeout=15.0,
                transport=self._transport,
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {self._access_token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            ) as client:
                response = await client.get(endpoint, params=params)
        except httpx.HTTPError as error:
            raise GitHubIngestionUnavailableError("GitHub evidence request failed") from error
        if response.status_code in {401, 403, 429} or response.status_code >= 500:
            raise GitHubIngestionUnavailableError("GitHub evidence request is unavailable")
        if response.is_error:
            raise GitHubIngestionError("GitHub evidence request was rejected")
        return response

    @staticmethod
    def _list_params(endpoint: str, page: int) -> dict[str, object]:
        params: dict[str, object] = {"per_page": 100, "page": page}
        if endpoint == "/user/repos":
            params.update({"affiliation": "owner,collaborator,organization_member", "sort": "full_name"})
        elif endpoint.endswith("/pulls"):
            params["state"] = "all"
        return params

    @staticmethod
    def _json_list(response: httpx.Response) -> list[dict[str, object]]:
        try:
            payload = response.json()
        except ValueError as error:
            raise GitHubIngestionError("GitHub evidence response is invalid") from error
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise GitHubIngestionError("GitHub evidence response must be a list")
        return payload

    @staticmethod
    def _next_page(response: httpx.Response) -> int | None:
        next_link = response.links.get("next", {}).get("url")
        if not next_link:
            return None
        page_values = parse_qs(urlparse(next_link).query).get("page")
        if not page_values or not page_values[0].isdigit():
            raise GitHubIngestionError("GitHub pagination link is invalid")
        return int(page_values[0])

    @classmethod
    def _repository_artifact(cls, repository: dict[str, object]) -> GitHubArtifact:
        repository_id = cls._required_int(repository, "id")
        full_name = cls._required_string(repository, "full_name")
        owner, name = cls._repository_path(full_name)
        owner_data = cls._required_dict(repository, "owner")
        payload = {
            "github_id": repository_id,
            "full_name": full_name,
            "owner_login": cls._required_string(owner_data, "login"),
            "name": name,
            "html_url": cls._required_string(repository, "html_url"),
            "default_branch": cls._optional_string(repository, "default_branch"),
            "is_fork": cls._required_bool(repository, "fork"),
            "is_private": cls._required_bool(repository, "private"),
            "pushed_at": cls._optional_string(repository, "pushed_at"),
            "updated_at": cls._optional_string(repository, "updated_at"),
        }
        return GitHubArtifact(
            source_type="github_repository",
            source_ref=f"github:repository:{repository_id}",
            payload=payload,
            observed_at=payload["updated_at"],
        )

    @classmethod
    def _commit_artifact(cls, commit: dict[str, object], repository_id: int) -> GitHubArtifact:
        commit_data = cls._required_dict(commit, "commit")
        author_data = cls._required_dict(commit_data, "author")
        sha = cls._required_string(commit, "sha")
        payload = {
            "sha": sha,
            "html_url": cls._required_string(commit, "html_url"),
            "message": cls._required_string(commit_data, "message"),
            "author_name": cls._required_string(author_data, "name"),
            "author_email": cls._required_string(author_data, "email"),
            "authored_at": cls._required_string(author_data, "date"),
            "github_author_login": cls._nested_optional_string(commit, "author", "login"),
        }
        return GitHubArtifact(
            source_type="github_commit",
            source_ref=f"github:commit:{repository_id}:{sha}",
            payload=payload,
            observed_at=payload["authored_at"],
        )

    @classmethod
    def _pull_request_artifact(cls, pull_request: dict[str, object], repository_id: int) -> GitHubArtifact:
        number = cls._required_int(pull_request, "number")
        payload = {
            "number": number,
            "html_url": cls._required_string(pull_request, "html_url"),
            "title": cls._required_string(pull_request, "title"),
            "state": cls._required_string(pull_request, "state"),
            "created_at": cls._required_string(pull_request, "created_at"),
            "updated_at": cls._required_string(pull_request, "updated_at"),
            "merged_at": cls._optional_string(pull_request, "merged_at"),
            "author_login": cls._nested_optional_string(pull_request, "user", "login"),
            "base_ref": cls._nested_required_string(pull_request, "base", "ref"),
            "head_ref": cls._nested_required_string(pull_request, "head", "ref"),
        }
        return GitHubArtifact(
            source_type="github_pull_request",
            source_ref=f"github:pull_request:{repository_id}:{number}",
            payload=payload,
            observed_at=payload["updated_at"],
        )

    @classmethod
    def _release_artifact(cls, release: dict[str, object], repository_id: int) -> GitHubArtifact:
        release_id = cls._required_int(release, "id")
        payload = {
            "github_id": release_id,
            "html_url": cls._required_string(release, "html_url"),
            "tag_name": cls._required_string(release, "tag_name"),
            "name": cls._optional_string(release, "name"),
            "is_draft": cls._required_bool(release, "draft"),
            "is_prerelease": cls._required_bool(release, "prerelease"),
            "published_at": cls._optional_string(release, "published_at"),
            "author_login": cls._nested_optional_string(release, "author", "login"),
        }
        return GitHubArtifact(
            source_type="github_release",
            source_ref=f"github:release:{repository_id}:{release_id}",
            payload=payload,
            observed_at=payload["published_at"],
        )

    @staticmethod
    def _repository_path(full_name: str) -> tuple[str, str]:
        parts = full_name.split("/", maxsplit=1)
        if len(parts) != 2 or not all(parts):
            raise GitHubIngestionError("GitHub repository full name is invalid")
        return parts[0], parts[1]

    @staticmethod
    def _required_string(payload: dict[str, object], name: str) -> str:
        value = payload.get(name)
        if not isinstance(value, str) or not value:
            raise GitHubIngestionError(f"GitHub field {name} is invalid")
        return value

    @staticmethod
    def _optional_string(payload: dict[str, object], name: str) -> str | None:
        value = payload.get(name)
        if value is None:
            return None
        if not isinstance(value, str):
            raise GitHubIngestionError(f"GitHub field {name} is invalid")
        return value

    @staticmethod
    def _required_int(payload: dict[str, object], name: str) -> int:
        value = payload.get(name)
        if not isinstance(value, int) or isinstance(value, bool):
            raise GitHubIngestionError(f"GitHub field {name} is invalid")
        return value

    @staticmethod
    def _required_bool(payload: dict[str, object], name: str) -> bool:
        value = payload.get(name)
        if not isinstance(value, bool):
            raise GitHubIngestionError(f"GitHub field {name} is invalid")
        return value

    @staticmethod
    def _required_dict(payload: dict[str, object], name: str) -> dict[str, object]:
        value = payload.get(name)
        if not isinstance(value, dict):
            raise GitHubIngestionError(f"GitHub field {name} is invalid")
        return value

    @classmethod
    def _nested_required_string(
        cls,
        payload: dict[str, object],
        parent: str,
        name: str,
    ) -> str:
        return cls._required_string(cls._required_dict(payload, parent), name)

    @classmethod
    def _nested_optional_string(
        cls,
        payload: dict[str, object],
        parent: str,
        name: str,
    ) -> str | None:
        value = payload.get(parent)
        if value is None:
            return None
        if not isinstance(value, dict):
            raise GitHubIngestionError(f"GitHub field {parent} is invalid")
        return cls._optional_string(value, name)