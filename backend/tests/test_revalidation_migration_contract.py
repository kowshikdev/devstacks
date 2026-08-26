from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202608260008_targeted_revalidation.sql"
)


def test_migration_traverses_claim_evidence_links_scoped_to_the_profile_and_artifact():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "create or replace function public.find_affected_claim_revisions" in migration
    assert "version.source_artifact_id = p_source_artifact_id" in migration
    assert "version.profile_id = p_profile_id" in migration
    assert "revision.profile_id = p_profile_id" in migration
    assert "link.evidence_version_id <> p_changed_evidence_version_id" in migration


def test_migration_records_freshness_assessments_without_touching_publication_history():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "create or replace function public.record_freshness_assessment" in migration
    assert "claim revision does not belong to the profile" in migration
    assert "insert into public.freshness_assessments" in migration
    assert "verification_decisions" not in migration
    assert "review_decisions" not in migration
    assert "publications" not in migration


def test_migration_limits_write_and_traversal_rpcs_to_the_service_role():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert migration.count("security definer") == 2
    assert migration.count("set search_path = ''") == 2
    assert migration.count("to service_role") == 2
    assert "from public, anon, authenticated" in migration
