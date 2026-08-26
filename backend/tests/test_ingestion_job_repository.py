import asyncio
from uuid import uuid4

import httpx
import pytest

from devstacks_api.repositories import (
    RepositoryUnavailableError,
    SupabaseIngestionJobRepository,
    SupabaseServiceSettings,
)
from devstacks_domain import IngestionStatus


RUN_ID = str(uuid4())
PROFILE_ID = str(uuid4())
CONNECTION_ID = str(uuid4())
WORKER_ID = "worker-1"


def repository(handler):
    return SupabaseIngestionJobRepository(
        SupabaseServiceSettings(
            url="https://project.supabase.co",
            service_role_key="server-only-key",
        ),
        transport=httpx.MockTransport(handler),
    )


def lease_payload() -> dict[str, object]:
    return {
        "id": RUN_ID,
        "profile_id": PROFILE_ID,
        "connection_id": CONNECTION_ID,
        "attempt_count": 2,
        "lease_owner": WORKER_ID,
        "lease_expires_at": "2026-08-26T00:01:00+00:00",
    }


def test_worker_claims_one_run_through_server_only_rpc():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/claim_ingestion_run"
        assert request.headers["apikey"] == "server-only-key"
        assert request.headers.get("authorization") is None
        return httpx.Response(200, json=lease_payload())

    lease = asyncio.run(repository(handler).claim(WORKER_ID, lease_seconds=120))

    assert lease is not None
    assert lease.id == RUN_ID
    assert lease.attempt_count == 2
    assert lease.connection_id == CONNECTION_ID


def test_worker_accepts_no_work_from_null_claim_response():
    lease = asyncio.run(
        repository(lambda request: httpx.Response(200, json=None)).claim(WORKER_ID)
    )

    assert lease is None


def test_worker_completes_only_with_its_claimed_lease_owner():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("claim_ingestion_run"):
            return httpx.Response(200, json=lease_payload())
        return httpx.Response(200, json={"id": RUN_ID})

    job_repository = repository(handler)
    lease = asyncio.run(job_repository.claim(WORKER_ID))
    assert lease is not None

    asyncio.run(job_repository.complete(lease, IngestionStatus.NO_OP))

    assert requests[-1].url.path == "/rest/v1/rpc/complete_ingestion_run"


@pytest.mark.parametrize(
    ("worker_id", "lease_seconds"),
    [("", 60), (WORKER_ID, 0), (WORKER_ID, 3601)],
)
def test_worker_claim_rejects_invalid_lease_inputs(worker_id, lease_seconds):
    with pytest.raises(ValueError):
        asyncio.run(
            repository(lambda request: httpx.Response(200, json=None)).claim(
                worker_id,
                lease_seconds,
            )
        )


def test_worker_rejects_non_terminal_completion_status():
    lease = repository(lambda request: httpx.Response(200, json=None))._parse_lease(
        lease_payload(),
        WORKER_ID,
    )

    with pytest.raises(ValueError, match="terminal"):
        asyncio.run(
            repository(lambda request: httpx.Response(200, json={})).complete(
                lease,
                IngestionStatus.RUNNING,
            )
        )


def test_worker_rejects_lease_owned_by_another_worker():
    response = {**lease_payload(), "lease_owner": "worker-2"}

    with pytest.raises(RepositoryUnavailableError, match="worker scope"):
        asyncio.run(
            repository(lambda request: httpx.Response(200, json=response)).claim(WORKER_ID)
        )


def test_worker_queues_a_profile_scoped_github_ingestion_run():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/enqueue_github_ingestion_run"
        return httpx.Response(
            200,
            json={"id": RUN_ID, "profile_id": PROFILE_ID, "connection_id": CONNECTION_ID},
        )

    run_id = asyncio.run(
        repository(handler).enqueue_github(PROFILE_ID, CONNECTION_ID, "initial-github-sync")
    )

    assert run_id == RUN_ID