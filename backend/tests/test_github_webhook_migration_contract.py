from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202608260007_github_webhook_delivery.sql"
)


def test_webhook_migration_maps_an_active_hook_to_one_github_connection():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "create table public.github_webhook_subscriptions" in migration
    assert "github_hook_id bigint not null unique" in migration
    assert "unique (connection_id, github_repository_id)" in migration
    assert "connection_status = 'active'" in migration
    assert "alter table public.github_webhook_subscriptions enable row level security" in migration


def test_webhook_migration_deduplicates_delivery_and_queues_only_relevant_events():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "create or replace function public.process_github_webhook_delivery" in migration
    assert "on conflict (connection_id, provider_event_id) do nothing" in migration
    assert "delivery_exists boolean := false" in migration
    assert "if p_event_type in ('push', 'pull_request', 'release')" in migration
    assert "'github-webhook:' || p_provider_event_id" in migration
    assert "'webhook'" in migration


def test_webhook_migration_limits_subscription_and_delivery_functions_to_service_role():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert migration.count("security definer") == 2
    assert migration.count("set search_path = ''") == 2
    assert migration.count("to service_role") == 2
    assert "from public, anon, authenticated" in migration