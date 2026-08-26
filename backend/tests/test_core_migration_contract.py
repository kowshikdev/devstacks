from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "202608250001_core_evidence_graph.sql"
)


def test_core_migration_defines_the_versioned_provenance_graph():
    migration = MIGRATION_PATH.read_text(encoding="utf-8")

    for table_name in (
        "profiles",
        "source_connections",
        "source_subjects",
        "identity_bindings",
        "ingestion_runs",
        "source_artifacts",
        "evidence_versions",
        "claims",
        "claim_revisions",
        "claim_evidence_links",
        "verification_decisions",
        "review_decisions",
        "policy_versions",
        "publications",
        "freshness_assessments",
        "agent_runs",
        "audit_events",
    ):
        assert f"create table public.{table_name}" in migration
        assert f"alter table public.{table_name} enable row level security" in migration

    assert "unique (source_artifact_id, version_number)" in migration
    assert "unique (claim_id, revision_number)" in migration
    assert "evidence_relation as enum ('supports', 'contradicts', 'context')" in migration
    assert "verification_decision_id uuid not null" in migration


def test_core_migration_indexes_foreign_key_traversal_paths():
    migration = MIGRATION_PATH.read_text(encoding="utf-8")

    for index_name in (
        "evidence_versions_source_artifact_id_idx",
        "identity_bindings_source_subject_id_idx",
        "ingestion_runs_connection_id_idx",
        "claim_revisions_claim_id_idx",
        "claim_evidence_links_evidence_version_id_idx",
        "verification_decisions_claim_revision_id_idx",
        "review_decisions_claim_revision_id_idx",
        "publications_claim_revision_id_idx",
        "freshness_assessments_claim_revision_id_idx",
    ):
        assert f"create index {index_name}" in migration


def test_tenant_migration_keeps_client_access_read_only():
    migration_path = MIGRATION_PATH.with_name("202608250002_tenant_rls.sql")
    migration = migration_path.read_text(encoding="utf-8")

    assert "security definer" in migration
    assert "set search_path = ''" in migration
    assert "for select to authenticated" in migration
    assert "for insert to authenticated" not in migration
    assert "for update to authenticated" not in migration
    assert "for delete to authenticated" not in migration
    assert "private.owns_claim_revision(claim_revision_id)" in migration
    assert "private.owns_evidence_version(evidence_version_id)" in migration