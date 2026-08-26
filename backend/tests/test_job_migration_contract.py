from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "202608260003_ingestion_job_leases.sql"
)


def test_job_migration_defines_leases_and_provider_event_deduplication():
    migration = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "add column attempt_count integer not null default 0" in migration
    assert "add column lease_owner text" in migration
    assert "add column lease_expires_at timestamptz" in migration
    assert "create index ingestion_runs_claimable_idx" in migration
    assert "create table public.provider_events" in migration
    assert "unique (connection_id, provider_event_id)" in migration
    assert "alter table public.provider_events enable row level security" in migration
    assert "create or replace function public.record_provider_event" in migration
    assert "source connection does not belong to the profile" in migration
    assert "on conflict (connection_id, provider_event_id) do nothing" in migration


def test_job_claim_rpc_is_atomic_and_non_blocking():
    migration = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "create or replace function public.claim_ingestion_run" in migration
    assert "for update skip locked" in migration
    assert "attempt_count = run.attempt_count + 1" in migration
    assert "lease_owner = p_worker_id" in migration
    assert "lease_expires_at = now() + make_interval" in migration
    assert "returning run.* into claimed_run" in migration
    assert "if not found then\n    return null;" in migration


def test_job_completion_requires_the_active_lease_owner_and_terminal_status():
    migration = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "create or replace function public.complete_ingestion_run" in migration
    assert "p_status not in ('succeeded', 'partial', 'failed', 'no_op')" in migration
    assert "and lease_owner = p_worker_id" in migration
    assert "and lease_expires_at > now()" in migration
    assert "lease_owner = null" in migration
    assert "lease_expires_at = null" in migration
    assert "if not found then\n    raise exception 'ingestion run is not actively leased by this worker';" in migration


def test_job_rpcs_are_security_hardened_and_service_role_only():
    migration = MIGRATION_PATH.read_text(encoding="utf-8")

    assert migration.count("security definer") == 3
    assert migration.count("set search_path = ''") == 3
    assert "from public, anon, authenticated" in migration
    assert "grant execute on function public.claim_ingestion_run(text, integer) to service_role" in migration
    assert "grant execute on function public.complete_ingestion_run(uuid, text, text, text) to service_role" in migration
    assert "grant execute on function public.record_provider_event(uuid, uuid, text, text, jsonb) to service_role" in migration