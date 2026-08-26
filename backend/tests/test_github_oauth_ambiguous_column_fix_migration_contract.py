from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202608260011_fix_github_oauth_ambiguous_column.sql"
)


def test_migration_adds_the_variable_conflict_pragma():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "create or replace function public.complete_github_authorization" in migration
    assert "#variable_conflict use_column" in migration
    # The pragma must precede any declare/begin block to take effect.
    pragma_index = migration.index("#variable_conflict use_column")
    declare_index = migration.index("declare")
    assert pragma_index < declare_index


def test_migration_preserves_the_external_return_shape():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "returns table (\n  connection_id uuid,\n  source_subject_id uuid\n)" in migration


def test_migration_keeps_the_rpc_service_role_only():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert migration.count("security definer") == 1
    assert migration.count("set search_path = ''") == 1
    assert "from public, anon, authenticated" in migration
    assert "to service_role" in migration
