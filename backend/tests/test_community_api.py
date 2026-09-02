import pytest
from fastapi.testclient import TestClient

from devstacks_api.auth import AuthenticatedUser
from devstacks_api.main import app
from devstacks_api.repositories import (
    CommunityAuthor,
    CommunityPost,
    CommunityPostRecord,
    CommunitySpace,
)
from devstacks_domain import ModerationAction, ModerationVerdict, TenantContext

# Assembled rather than written as a literal, so nothing credential-shaped is
# committed for a secret scanner to flag. See tests/test_moderation.py.
LEAKED_TOKEN = "ghp" + "_" + "abcdefghijklmnopqrstuvwxyz0123456789"


class FakeVerifier:
    async def validate(self, access_token: str) -> AuthenticatedUser:
        return AuthenticatedUser(id="profile-1", email="developer@example.com")


HELP_SPACE = CommunitySpace(
    id="space-1",
    slug="help",
    name="Help & debugging",
    description="Stuck on something real.",
    topic_categories=("domain.distributed-systems",),
    allowed_intents=("help_request", "discussion"),
)

AUTHOR = CommunityAuthor(
    profile_id="profile-1",
    handle="devstacks",
    display_name="Dev Stacks",
    verified_categories=("domain.distributed-systems",),
)

THREAD = CommunityPost(
    id="post-1",
    space_slug="help",
    parent_post_id=None,
    title="Idempotent webhook delivery",
    body="How do I make webhook delivery idempotent across retries?",
    intent="help_request",
    visibility="published",
    reply_count=1,
    created_at="2026-08-26T00:00:00+00:00",
    author=AUTHOR,
)

REPLY = CommunityPost(
    id="post-2",
    space_slug="help",
    parent_post_id="post-1",
    title=None,
    body="Store the delivery id and make the write conditional on it.",
    intent="discussion",
    visibility="published",
    reply_count=0,
    created_at="2026-08-26T01:00:00+00:00",
    author=AUTHOR,
)


class FakeCommunityRepository:
    def __init__(self, space: CommunitySpace | None = HELP_SPACE) -> None:
        self._space = space
        self.created: list[tuple[str, str | None, str, ModerationVerdict]] = []

    async def list_spaces(self):
        return (HELP_SPACE,)

    async def get_space(self, slug: str):
        return self._space

    async def list_threads(self, slug: str, limit: int = 50):
        return (THREAD,)

    async def get_thread(self, post_id: str):
        return (THREAD, REPLY) if post_id == "post-1" else ()

    async def create_post(self, tenant, space_slug, parent_post_id, title, body, verdict):
        assert isinstance(tenant, TenantContext)
        self.created.append((space_slug, title, body, verdict))
        return CommunityPostRecord(post_id="post-9", decision_id="decision-9")


def _client(repository: FakeCommunityRepository) -> TestClient:
    app.state.access_token_verifier = FakeVerifier()
    app.state.community_repository = repository
    return TestClient(app)


def _teardown() -> None:
    del app.state.access_token_verifier
    del app.state.community_repository


AUTH = {"Authorization": "Bearer user-access-token"}


def test_spaces_are_readable_without_an_account():
    repository = FakeCommunityRepository()
    try:
        response = _client(repository).get("/v1/community/spaces")
    finally:
        _teardown()

    assert response.status_code == 200
    assert response.json()["spaces"][0]["slug"] == "help"


def test_a_thread_carries_its_authors_verified_categories_not_a_score():
    repository = FakeCommunityRepository()
    try:
        response = _client(repository).get("/v1/community/posts/post-1")
    finally:
        _teardown()

    assert response.status_code == 200
    author = response.json()["thread"]["author"]
    assert author["verified_categories"] == ["domain.distributed-systems"]
    assert "reputation" not in author
    assert "karma" not in author


def test_an_unknown_thread_is_not_found():
    repository = FakeCommunityRepository()
    try:
        response = _client(repository).get("/v1/community/posts/nope")
    finally:
        _teardown()

    assert response.status_code == 404


# ------------------------------------------------------------------- preflight


def test_preflight_warns_without_storing_anything():
    repository = FakeCommunityRepository()
    try:
        response = _client(repository).post(
            "/v1/community/preflight",
            headers=AUTH,
            json={"body": f"my token is {LEAKED_TOKEN}"},
        )
    finally:
        _teardown()

    assert response.status_code == 200
    assert response.json()["action"] == "block"
    assert "rotate" in response.json()["rationale"].lower()
    assert repository.created == []


def test_preflight_requires_a_bearer_token():
    repository = FakeCommunityRepository()
    try:
        response = _client(repository).post("/v1/community/preflight", json={"body": "hello"})
    finally:
        _teardown()

    assert response.status_code == 401


def test_preflight_rejects_an_empty_draft():
    repository = FakeCommunityRepository()
    try:
        response = _client(repository).post(
            "/v1/community/preflight", headers=AUTH, json={"body": "   "}
        )
    finally:
        _teardown()

    assert response.status_code == 400


# ----------------------------------------------------------------- posting


def test_a_clean_thread_is_published():
    repository = FakeCommunityRepository()
    try:
        response = _client(repository).post(
            "/v1/community/spaces/help/posts",
            headers=AUTH,
            json={
                "title": "Idempotent webhook delivery",
                "body": "How do I make webhook delivery idempotent across retries?",
            },
        )
    finally:
        _teardown()

    assert response.status_code == 200
    assert response.json()["published"] is True
    assert len(repository.created) == 1


def test_a_thread_needs_a_title():
    repository = FakeCommunityRepository()
    try:
        response = _client(repository).post(
            "/v1/community/spaces/help/posts",
            headers=AUTH,
            json={"body": "How do I do this?"},
        )
    finally:
        _teardown()

    assert response.status_code == 400
    assert repository.created == []


def test_a_blocked_post_is_still_recorded_with_its_reason():
    repository = FakeCommunityRepository()
    try:
        response = _client(repository).post(
            "/v1/community/spaces/help/posts",
            headers=AUTH,
            json={
                "title": "help with my config",
                "body": f"it fails with token {LEAKED_TOKEN}",
            },
        )
    finally:
        _teardown()

    assert response.status_code == 200
    assert response.json()["published"] is False
    assert response.json()["verdict"]["action"] == "block"
    # The author must be able to find out why, so the post and verdict are kept.
    assert len(repository.created) == 1
    assert repository.created[0][3].action is ModerationAction.BLOCK


def test_the_title_is_judged_alongside_the_body():
    repository = FakeCommunityRepository()
    try:
        response = _client(repository).post(
            "/v1/community/spaces/help/posts",
            headers=AUTH,
            json={"title": "you are an idiot", "body": "why does this keep happening"},
        )
    finally:
        _teardown()

    assert response.status_code == 200
    assert response.json()["verdict"]["action"] == "hold_for_review"


def test_a_space_refuses_an_intent_it_does_not_accept():
    repository = FakeCommunityRepository()
    try:
        response = _client(repository).post(
            "/v1/community/spaces/help/posts",
            headers=AUTH,
            json={
                "title": "Senior platform engineer",
                "body": "We're hiring a senior platform engineer, remote, apply here",
            },
        )
    finally:
        _teardown()

    assert response.status_code == 400
    assert "does not accept" in response.json()["detail"]
    assert repository.created == []


def test_posting_to_an_unknown_space_is_not_found():
    repository = FakeCommunityRepository(space=None)
    try:
        response = _client(repository).post(
            "/v1/community/spaces/nope/posts",
            headers=AUTH,
            json={"title": "Hello", "body": "Is anyone here at all today?"},
        )
    finally:
        _teardown()

    assert response.status_code == 404


def test_posting_requires_a_bearer_token():
    repository = FakeCommunityRepository()
    try:
        response = _client(repository).post(
            "/v1/community/spaces/help/posts",
            json={"title": "Hello", "body": "Is anyone here at all today?"},
        )
    finally:
        _teardown()

    assert response.status_code == 401
    assert repository.created == []
