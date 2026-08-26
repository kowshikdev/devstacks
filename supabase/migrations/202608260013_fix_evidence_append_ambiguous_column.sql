-- Third instance of the same bug class as 202608260011/202608260012:
-- append_github_evidence_version's RETURNS TABLE output parameters
-- (source_artifact_id, version_number) collide with real column names
-- referenced bare in a WHERE/ORDER BY clause, causing "column reference is
-- ambiguous" (42702) on every call. This is the evidence-append RPC the
-- entire GitHub ingestion pipeline depends on (GH-002) — found via
-- proactive audit after the same bug surfaced twice elsewhere, before it
-- was ever exercised against a real GitHub sync. Same fix:
-- #variable_conflict use_column. External signature and return shape
-- are unchanged.

create or replace function public.append_github_evidence_version(
  p_profile_id uuid,
  p_connection_id uuid,
  p_source_type text,
  p_source_ref text,
  p_canonical_payload jsonb,
  p_content_hash text,
  p_connector_version text,
  p_observed_at timestamptz default null
)
returns table (
  source_artifact_id uuid,
  evidence_version_id uuid,
  outcome text,
  version_number integer
)
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_column
declare
  source_artifact public.source_artifacts;
  latest_version public.evidence_versions;
  appended_version public.evidence_versions;
begin
  if p_source_type not in (
    'github_repository',
    'github_commit',
    'github_pull_request',
    'github_release'
  )
    or char_length(trim(p_source_ref)) = 0
    or char_length(p_content_hash) <> 64
    or char_length(trim(p_connector_version)) = 0 then
    raise exception 'github evidence parameters are invalid';
  end if;
  if not exists (
    select 1
    from public.source_connections
    where id = p_connection_id
      and profile_id = p_profile_id
      and platform = 'github'
      and connection_status = 'active'
  ) then
    raise exception 'active github connection does not belong to the profile';
  end if;

  insert into public.source_artifacts (
    profile_id,
    connection_id,
    source_type,
    source_ref,
    observed_at
  )
  values (
    p_profile_id,
    p_connection_id,
    p_source_type,
    p_source_ref,
    p_observed_at
  )
  on conflict (profile_id, source_type, source_ref) do nothing;

  select * into source_artifact
  from public.source_artifacts
  where profile_id = p_profile_id
    and source_type = p_source_type
    and source_ref = p_source_ref
  for update;

  select * into latest_version
  from public.evidence_versions
  where source_artifact_id = source_artifact.id
  order by version_number desc
  limit 1;

  if found and latest_version.content_hash = p_content_hash then
    return query select source_artifact.id, latest_version.id, 'no_op', latest_version.version_number;
    return;
  end if;

  insert into public.evidence_versions (
    profile_id,
    source_artifact_id,
    version_number,
    canonical_payload,
    content_hash,
    connector_version,
    assurance_class,
    validity,
    observed_at
  )
  values (
    p_profile_id,
    source_artifact.id,
    coalesce(latest_version.version_number, 0) + 1,
    p_canonical_payload,
    p_content_hash,
    p_connector_version,
    'provider_observed',
    'current',
    p_observed_at
  )
  returning * into appended_version;

  return query select source_artifact.id, appended_version.id, 'create_version', appended_version.version_number;
end;
$$;

revoke all on function public.append_github_evidence_version(uuid, uuid, text, text, jsonb, text, text, timestamptz) from public, anon, authenticated;
grant execute on function public.append_github_evidence_version(uuid, uuid, text, text, jsonb, text, text, timestamptz) to service_role;
