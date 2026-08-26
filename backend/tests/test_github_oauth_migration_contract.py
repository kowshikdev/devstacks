from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202608260005_github_oauth_authorization.sql"
)


def test_github_oauth_migration_stores_only_hashed_state_and_encrypted_credentials():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "state_hash text not null unique" in migration
    assert "code_verifier_encrypted text not null" in migration
    assert "access_token_encrypted text not null" in migration
    assert "refresh_token_encrypted text" in migration
    assert "access_token text" not in migration
    assert "refresh_token text" not in migration


def test_github_oauth_migration_consumes_state_once_and_before_expiry():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "create or replace function public.consume_github_oauth_attempt" in migration
    assert "set consumed_at = now()" in migration
    assert "consumed_at is null" in migration
    assert "expires_at > now()" in migration


def test_github_oauth_migration_confirms_identity_and_limits_rpc_access():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "'provider_observed'" in migration
    assert "'confirmed'" in migration
    assert "alter table public.github_oauth_attempts enable row level security" in migration
    assert "alter table public.github_connection_credentials enable row level security" in migration
    assert migration.count("security definer") == 3
    assert migration.count("set search_path = ''") == 3
    assert "to service_role" in migration