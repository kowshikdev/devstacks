-- DevStacks tenant isolation.
-- Ownership checks run in private security-definer helpers to avoid RLS recursion
-- when child-table policies traverse the profile-owned evidence graph.

create schema if not exists private;
revoke all on schema private from public;

create or replace function private.owns_profile(target_profile_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.profiles
    where id = target_profile_id
      and id = (select auth.uid())
  );
$$;

create or replace function private.owns_claim_revision(target_claim_revision_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.claim_revisions
    where id = target_claim_revision_id
      and profile_id = (select auth.uid())
  );
$$;

create or replace function private.owns_evidence_version(target_evidence_version_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.evidence_versions
    where id = target_evidence_version_id
      and profile_id = (select auth.uid())
  );
$$;

revoke all on function private.owns_profile(uuid) from public;
revoke all on function private.owns_claim_revision(uuid) from public;
revoke all on function private.owns_evidence_version(uuid) from public;
grant usage on schema private to authenticated;
grant execute on function private.owns_profile(uuid) to authenticated;
grant execute on function private.owns_claim_revision(uuid) to authenticated;
grant execute on function private.owns_evidence_version(uuid) to authenticated;

create policy "profiles_select_own" on public.profiles
  for select to authenticated using (id = (select auth.uid()));
do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'source_connections',
    'source_subjects',
    'identity_bindings',
    'ingestion_runs',
    'source_artifacts',
    'evidence_versions',
    'claims',
    'claim_revisions',
    'agent_runs',
    'verification_decisions',
    'review_decisions',
    'policy_versions',
    'publications',
    'freshness_assessments',
    'audit_events'
  ]
  loop
    execute format(
      'create policy %I on public.%I for select to authenticated using (private.owns_profile(profile_id))',
      table_name || '_select_own', table_name
    );
  end loop;
end;
$$;

create policy "claim_evidence_links_select_own" on public.claim_evidence_links
  for select to authenticated
  using (
    private.owns_claim_revision(claim_revision_id)
    and private.owns_evidence_version(evidence_version_id)
  );

-- Authenticated clients can read their graph but cannot mutate it directly.
-- FastAPI validates the caller and uses the service role for audited writes.