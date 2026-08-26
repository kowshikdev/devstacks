create or replace function public.get_github_connection_credential(
  p_profile_id uuid,
  p_connection_id uuid
)
returns table (
  access_token_encrypted text
)
language sql
stable
security definer
set search_path = ''
as $$
  select credential.access_token_encrypted
  from public.source_connections as connection
  join public.github_connection_credentials as credential
    on credential.connection_id = connection.id
  where connection.id = p_connection_id
    and connection.profile_id = p_profile_id
    and connection.platform = 'github'
    and connection.connection_status = 'active';
$$;

create or replace function public.enqueue_github_ingestion_run(
  p_profile_id uuid,
  p_connection_id uuid,
  p_idempotency_key text
)
returns public.ingestion_runs
language plpgsql
security definer
set search_path = ''
as $$
declare
  ingestion_run public.ingestion_runs;
begin
  if char_length(trim(p_idempotency_key)) = 0 then
    raise exception 'github ingestion idempotency key is required';
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

  insert into public.ingestion_runs (
    profile_id,
    connection_id,
    trigger_type,
    status,
    idempotency_key
  )
  values (
    p_profile_id,
    p_connection_id,
    'manual',
    'queued',
    p_idempotency_key
  )
  on conflict (profile_id, idempotency_key) do update
  set id = public.ingestion_runs.id
  returning * into ingestion_run;

  if ingestion_run.connection_id <> p_connection_id then
    raise exception 'github ingestion idempotency key belongs to another connection';
  end if;
  return ingestion_run;
end;
$$;

create or replace function private.queue_initial_github_ingestion()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  connection_profile_id uuid;
begin
  select profile_id into connection_profile_id
  from public.source_connections
  where id = new.connection_id
    and platform = 'github'
    and connection_status = 'active';

  if connection_profile_id is not null then
    insert into public.ingestion_runs (
      profile_id,
      connection_id,
      trigger_type,
      status,
      idempotency_key
    )
    values (
      connection_profile_id,
      new.connection_id,
      'manual',
      'queued',
      'github-authorized:' || new.connection_id::text
    )
    on conflict (profile_id, idempotency_key) do update
    set id = public.ingestion_runs.id;
  end if;
  return new;
end;
$$;

create trigger queue_initial_github_ingestion
  after insert or update of access_token_encrypted on public.github_connection_credentials
  for each row execute function private.queue_initial_github_ingestion();

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

revoke all on function public.get_github_connection_credential(uuid, uuid) from public, anon, authenticated;
revoke all on function public.enqueue_github_ingestion_run(uuid, uuid, text) from public, anon, authenticated;
revoke all on function public.append_github_evidence_version(uuid, uuid, text, text, jsonb, text, text, timestamptz) from public, anon, authenticated;
grant execute on function public.get_github_connection_credential(uuid, uuid) to service_role;
grant execute on function public.enqueue_github_ingestion_run(uuid, uuid, text) to service_role;
grant execute on function public.append_github_evidence_version(uuid, uuid, text, text, jsonb, text, text, timestamptz) to service_role;