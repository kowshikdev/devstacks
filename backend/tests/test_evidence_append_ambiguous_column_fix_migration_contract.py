from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202608260013_fix_evidence_append_ambiguous_column.sql"
)


def test_migration_adds_the_variable_conflict_pragma():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "create or replace function public.append_github_evidence_version" in migration
    assert "#variable_conflict use_column" in migration
    pragma_index = migration.index("#variable_conflict use_column")
    declare_index = migration.index("declare")
    assert pragma_index < declare_index


def test_migration_preserves_the_external_return_shape():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert (
        "returns table (\n  source_artifact_id uuid,\n  evidence_version_id uuid,\n  outcome text,\n  version_number integer\n)"
        in migration
    )


def test_migration_keeps_the_rpc_service_role_only():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert migration.count("security definer") == 1
    assert migration.count("set search_path = ''") == 1
    assert "from public, anon, authenticated" in migration
    assert "to service_role" in migration
