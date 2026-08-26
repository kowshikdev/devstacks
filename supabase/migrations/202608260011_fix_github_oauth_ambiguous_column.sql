-- Fixes a live-testing bug in complete_github_authorization: its RETURNS
-- TABLE output parameters (connection_id, source_subject_id) collide with
-- real column names used inside the function body, causing Postgres to
-- reject every call with "column reference is ambiguous" (42702). The
-- #variable_conflict pragma tells PL/pgSQL to prefer the table-column
-- reading in that ambiguity, which is what every statement here actually
-- means; the function's external signature and return shape are unchanged.

create or replace function public.complete_github_authorization(
  p_profile_id uuid,
  p_github_subject_id text,
  p_github_login text,
  p_access_token_encrypted text,
  p_refresh_token_encrypted text default null,
  p_access_token_expires_at timestamptz default null,
  p_refresh_token_expires_at timestamptz default null,
  p_scopes text[] default '{}'
)
returns table (
  connection_id uuid,
  source_subject_id uuid
)
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_column
declare
  github_connection public.source_connections;
  github_subject public.source_subjects;
begin
  if char_length(trim(p_github_subject_id)) = 0
    or char_length(trim(p_github_login)) = 0
    or char_length(trim(p_access_token_encrypted)) = 0 then
    raise exception 'github authorization parameters are invalid';
  end if;

  insert into public.source_connections (
    profile_id,
    platform,
    external_subject,
    connection_status,
    connected_at,
    last_synced_at
  )
  values (
    p_profile_id,
    'github',
    p_github_subject_id,
    'active',
    now(),
    now()
  )
  on conflict (profile_id, platform, external_subject) do update
  set connection_status = 'active',
      connected_at = excluded.connected_at
  returning * into github_connection;

  insert into public.source_subjects (
    profile_id,
    connection_id,
    provider_subject_id,
    provider_login,
    observed_at
  )
  values (
    p_profile_id,
    github_connection.id,
    p_github_subject_id,
    p_github_login,
    now()
  )
  on conflict (connection_id, provider_subject_id) do update
  set provider_login = excluded.provider_login,
      observed_at = excluded.observed_at
  returning * into github_subject;

  insert into public.identity_bindings (
    profile_id,
    source_subject_id,
    assurance_class,
    status,
    confirmed_at
  )
  values (
    p_profile_id,
    github_subject.id,
    'provider_observed',
    'confirmed',
    now()
  )
  on conflict (profile_id, source_subject_id) do update
  set assurance_class = excluded.assurance_class,
      status = excluded.status,
      confirmed_at = excluded.confirmed_at;

  insert into public.github_connection_credentials (
    connection_id,
    access_token_encrypted,
    refresh_token_encrypted,
    access_token_expires_at,
    refresh_token_expires_at,
    scopes,
    updated_at
  )
  values (
    github_connection.id,
    p_access_token_encrypted,
    p_refresh_token_encrypted,
    p_access_token_expires_at,
    p_refresh_token_expires_at,
    p_scopes,
    now()
  )
  on conflict (connection_id) do update
  set access_token_encrypted = excluded.access_token_encrypted,
      refresh_token_encrypted = excluded.refresh_token_encrypted,
      access_token_expires_at = excluded.access_token_expires_at,
      refresh_token_expires_at = excluded.refresh_token_expires_at,
      scopes = excluded.scopes,
      updated_at = excluded.updated_at;

  return query select github_connection.id, github_subject.id;
end;
$$;

revoke all on function public.complete_github_authorization(uuid, text, text, text, text, timestamptz, timestamptz, text[]) from public, anon, authenticated;
grant execute on function public.complete_github_authorization(uuid, text, text, text, text, timestamptz, timestamptz, text[]) to service_role;
