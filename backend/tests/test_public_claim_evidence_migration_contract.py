import re
from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202608260014_public_claim_evidence_trail.sql"
)


def test_migration_projects_only_published_revisions_on_public_profiles():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "create or replace function public.get_published_claim_evidence" in migration
    assert "publication.status = 'published'" in migration
    assert "profile.is_public = true" in migration
    assert "claim_revision.id = p_claim_revision_id" in migration


def _executable_sql() -> str:
    """The migration with `--` comments stripped.

    Absence assertions have to run against what the database executes. The
    migration documents the columns it deliberately excludes, and prose naming
    a column must not read as the projection selecting it.
    """
    migration = MIGRATION.read_text(encoding="utf-8")
    return re.sub(r"--[^\n]*", "", migration)


def test_migration_never_projects_private_evidence_material():
    sql = _executable_sql()

    # The observed payload and the source reference stay private: a reference
    # can name a private repository, and the content hash proves integrity
    # without disclosing one.
    assert "canonical_payload" not in sql
    assert "source_ref" not in sql
    assert "version.content_hash" in sql


def test_migration_limits_the_rpc_to_the_service_role():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert migration.count("security definer") == 1
    assert migration.count("set search_path = ''") == 1
    assert "revoke all on function public.get_published_claim_evidence" in migration
    assert "from public, anon, authenticated" in migration
    assert "grant execute on function public.get_published_claim_evidence" in migration
    assert "to service_role" in migration
