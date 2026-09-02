import re
from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202608260015_community_spaces.sql"
)


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def test_migration_creates_the_community_tables():
    sql = _sql()

    for table in (
        "public.community_spaces",
        "public.community_posts",
        "public.moderation_decisions",
        "public.moderation_signals",
    ):
        assert f"create table {table}" in sql


def test_a_post_is_always_created_with_the_decision_that_admitted_it():
    sql = _sql()

    assert "create or replace function public.create_community_post" in sql
    assert "insert into public.community_posts" in sql
    assert "insert into public.moderation_decisions" in sql
    assert "insert into public.moderation_signals" in sql


def test_moderation_decisions_record_their_policy_version_and_rationale():
    sql = _sql()

    assert "policy_version text not null" in sql
    assert "rationale text not null" in sql


def test_only_published_posts_are_publicly_readable():
    sql = _sql()

    assert "community_posts_select_published" in sql
    assert "visibility = 'published'" in sql


def test_an_author_can_always_see_their_own_moderated_post_and_its_reasons():
    sql = _sql()

    assert "community_posts_select_own" in sql
    assert "moderation_decisions_select_own" in sql
    assert "moderation_signals_select_own" in sql
    assert sql.count("private.owns_profile") >= 3


def test_row_level_security_is_enabled_on_every_new_table():
    sql = _sql()

    for table in (
        "public.community_spaces",
        "public.community_posts",
        "public.moderation_decisions",
        "public.moderation_signals",
    ):
        assert f"alter table {table} enable row level security;" in sql


def test_the_write_rpc_is_limited_to_the_service_role():
    sql = _sql()

    assert sql.count("security definer") == 1
    assert sql.count("set search_path = ''") == 1
    assert "revoke all on function public.create_community_post" in sql
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql


def test_a_thread_has_a_title_and_a_reply_has_a_parent():
    sql = _sql()

    assert "community_posts_shape" in sql
    assert "parent_post_id is null and title is not null" in sql


def test_only_a_published_reply_counts_toward_its_thread():
    sql = _sql()

    assert "p_visibility = 'published'" in sql
    assert "set reply_count = reply_count + 1" in sql
