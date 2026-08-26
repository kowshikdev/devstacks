from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202608260006_github_evidence_persistence.sql"
)


def test_github_evidence_migration_retrieves_only_active_profile_scoped_credentials():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "create or replace function public.get_github_connection_credential" in migration
    assert "connection.profile_id = p_profile_id" in migration
    assert "connection.platform = 'github'" in migration
    assert "connection.connection_status = 'active'" in migration
    assert "access_token_encrypted" in migration


def test_github_evidence_migration_appends_or_returns_explicit_no_op_versions():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "create or replace function public.append_github_evidence_version" in migration
    assert "for update" in migration
    assert "latest_version.content_hash = p_content_hash" in migration
    assert "'no_op'" in migration
    assert "'create_version'" in migration
    assert "coalesce(latest_version.version_number, 0) + 1" in migration
    assert "'provider_observed'" in migration


def test_github_evidence_migration_queues_profile_scoped_idempotent_runs():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "create or replace function public.enqueue_github_ingestion_run" in migration
    assert "'manual'" in migration
    assert "'queued'" in migration
    assert "on conflict (profile_id, idempotency_key) do update" in migration
    assert "idempotency key belongs to another connection" in migration
    assert "create trigger queue_initial_github_ingestion" in migration
    assert "after insert or update of access_token_encrypted" in migration
    assert "'github-authorized:' || new.connection_id::text" in migration


def test_github_evidence_migration_limits_write_rpcs_to_the_service_role():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert migration.count("security definer") == 4
    assert migration.count("set search_path = ''") == 4
    assert migration.count("to service_role") == 3
    assert "from public, anon, authenticated" in migration