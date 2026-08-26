import asyncio
import json

import httpx
import pytest

from devstacks_api.github_ingestion import GitHubArtifact
from devstacks_api.repositories import (
    RepositoryUnavailableError,
    SupabaseGitHubEvidenceRepository,
    SupabaseServiceSettings,
)
from devstacks_domain import EvidenceVersionOutcome


def repository(handler):
    return SupabaseGitHubEvidenceRepository(
        SupabaseServiceSettings(
            url="https://project.supabase.co",
            service_role_key="server-only-key",
        ),
        transport=httpx.MockTransport(handler),
    )


def artifact() -> GitHubArtifact:
    return GitHubArtifact(
        source_type="github_repository",
        source_ref="github:repository:101",
        payload={"github_id": 101, "full_name": "octocat/hello-world"},
        observed_at="2026-08-26T00:00:00Z",
    )


def test_evidence_repository_reads_encrypted_token_only_through_scoped_rpc():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/get_github_connection_credential"
        assert request.headers["apikey"] == "server-only-key"
        assert request.headers.get("authorization") is None
        assert json.loads(request.content) == {
            "p_profile_id": "profile-1",
            "p_connection_id": "connection-1",
        }
        return httpx.Response(200, json=[{"access_token_encrypted": "ciphertext"}])

    value = asyncio.run(
        repository(handler).get_access_token_encrypted("profile-1", "connection-1")
    )

    assert value == "ciphertext"


def test_evidence_repository_appends_a_normalized_artifact_with_its_hash():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/append_github_evidence_version"
        body = json.loads(request.content)
        assert body["p_source_ref"] == "github:repository:101"
        assert body["p_content_hash"] == "a" * 64
        return httpx.Response(
            200,
            json={
                "outcome": "create_version",
                "version_number": 1,
                "source_artifact_id": "artifact-1",
                "evidence_version_id": "version-1",
            },
        )

    write = asyncio.run(
        repository(handler).append_evidence(
            "profile-1",
            "connection-1",
            artifact(),
            "a" * 64,
        )
    )

    assert write.outcome is EvidenceVersionOutcome.CREATE_VERSION
    assert write.version_number == 1
    assert write.source_artifact_id == "artifact-1"
    assert write.evidence_version_id == "version-1"


def test_evidence_repository_rejects_an_invalid_append_outcome():
    with pytest.raises(RepositoryUnavailableError, match="incomplete"):
        asyncio.run(
            repository(
                lambda request: httpx.Response(
                    200,
                    json={"outcome": "unknown", "version_number": 1},
                )
            ).append_evidence("profile-1", "connection-1", artifact(), "a" * 64)
        )