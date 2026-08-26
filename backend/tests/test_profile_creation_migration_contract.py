from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202608260010_profile_creation.sql"
)


def test_migration_creates_exactly_one_profile_per_authenticated_subject():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "create or replace function public.create_own_profile" in migration
    assert "profile id does not match an authenticated subject" in migration
    assert "profile already exists for this subject" in migration
    assert "insert into public.profiles" in migration


def test_migration_limits_the_rpc_to_the_service_role():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert migration.count("security definer") == 1
    assert migration.count("set search_path = ''") == 1
    assert "revoke all on function public.create_own_profile" in migration
    assert "from public, anon, authenticated" in migration
    assert "grant execute on function public.create_own_profile" in migration
    assert "to service_role" in migration
