from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202608260009_claims_verification_review_publication.sql"
)


def test_migration_creates_claim_revisions_with_tenant_scoped_evidence_links():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "create or replace function public.create_claim_revision" in migration
    assert "at least one evidence link is required" in migration
    assert "coalesce(max(revision.revision_number), 0) + 1" in migration
    assert "where id = link_evidence_version_id and profile_id = p_profile_id" in migration


def test_migration_defers_transition_enforcement_to_the_domain_layer():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "create or replace function public.record_verification_decision" in migration
    assert "create or replace function public.record_review_decision" in migration
    assert "review actor is required" in migration
    # These RPCs only tenant-scope and append; no transition-map enum sets appear
    # in the function bodies themselves (the file's header comment may reference
    # the domain layer by name, which is fine).
    assert "frozenset" not in migration


def test_migration_re_derives_publication_provenance_defensively():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "create or replace function public.record_publication" in migration
    assert "and status = 'verified'" in migration
    assert "and status = 'approved'" in migration
    assert "published status requires a published timestamp" in migration


def test_migration_leases_agent_runs_like_ingestion_runs():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "add column lease_owner text" in migration
    assert "add column lease_expires_at timestamptz" in migration
    assert "create or replace function public.claim_agent_run" in migration
    assert "create or replace function public.complete_agent_run" in migration
    assert "for update skip locked" in migration
    assert "'succeeded', 'failed', 'interrupted'" in migration


def test_migration_limits_every_new_rpc_to_the_service_role():
    migration = MIGRATION.read_text(encoding="utf-8")

    function_names = [
        "create_claim_revision",
        "record_verification_decision",
        "record_review_decision",
        "record_publication",
        "list_pending_claim_revisions",
        "get_claim_revision_evidence_links",
        "get_latest_verification_status",
        "get_latest_review_status",
        "get_claim_revision_publication_context",
        "get_evidence_version",
        "enqueue_claim_agent_run",
        "claim_agent_run",
        "complete_agent_run",
        "get_agent_run",
    ]
    for name in function_names:
        assert f"create or replace function public.{name}" in migration

    assert migration.count("security definer") == len(function_names)
    assert migration.count("set search_path = ''") == len(function_names)
    assert migration.count("to service_role") == len(function_names)
    assert "from public, anon, authenticated" in migration
