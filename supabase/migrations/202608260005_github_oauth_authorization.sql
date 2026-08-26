create table public.github_oauth_attempts (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  state_hash text not null unique check (char_length(state_hash) = 64),
  code_verifier_encrypted text not null,
  redirect_uri text not null,
  expires_at timestamptz not null,
  consumed_at timestamptz,
  created_at timestamptz not null default now(),
  constraint github_oauth_attempts_expiry check (expires_at > created_at)
);

create table public.github_connection_credentials (
  connection_id uuid primary key references public.source_connections(id) on delete cascade,
  access_token_encrypted text not null,
  refresh_token_encrypted text,
  access_token_expires_at timestamptz,
  refresh_token_expires_at timestamptz,
  scopes text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index github_oauth_attempts_expiry_idx
  on public.github_oauth_attempts (expires_at)
  where consumed_at is null;

alter table public.github_oauth_attempts enable row level security;
alter table public.github_connection_credentials enable row level security;

create or replace function public.create_github_oauth_attempt(
  p_profile_id uuid,
  p_state_hash text,
  p_code_verifier_encrypted text,
  p_redirect_uri text,
  p_expires_at timestamptz
)
returns public.github_oauth_attempts
language plpgsql
security definer
set search_path = ''
as $$
declare
  oauth_attempt public.github_oauth_attempts;
begin
  if char_length(p_state_hash) <> 64
    or char_length(trim(p_code_verifier_encrypted)) = 0
    or char_length(trim(p_redirect_uri)) = 0
    or p_expires_at <= now() then
    raise exception 'github oauth attempt parameters are invalid';
  end if;

  insert into public.github_oauth_attempts (
    profile_id,
    state_hash,
    code_verifier_encrypted,
    redirect_uri,
    expires_at
  )
  values (
    p_profile_id,
    p_state_hash,
    p_code_verifier_encrypted,
    p_redirect_uri,
    p_expires_at
  )
  returning * into oauth_attempt;

  return oauth_attempt;
end;
$$;

create or replace function public.consume_github_oauth_attempt(p_state_hash text)
returns table (
  profile_id uuid,
  code_verifier_encrypted text,
  redirect_uri text
)
language plpgsql
security definer
set search_path = ''
as $$
begin
  if char_length(p_state_hash) <> 64 then
    return;
  end if;

  return query
  update public.github_oauth_attempts
  set consumed_at = now()
  where state_hash = p_state_hash
    and consumed_at is null
    and expires_at > now()
  returning
    github_oauth_attempts.profile_id,
    github_oauth_attempts.code_verifier_encrypted,
    github_oauth_attempts.redirect_uri;
end;
$$;

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

revoke all on function public.create_github_oauth_attempt(uuid, text, text, text, timestamptz) from public, anon, authenticated;
revoke all on function public.consume_github_oauth_attempt(text) from public, anon, authenticated;
revoke all on function public.complete_github_authorization(uuid, text, text, text, text, timestamptz, timestamptz, text[]) from public, anon, authenticated;
grant execute on function public.create_github_oauth_attempt(uuid, text, text, text, timestamptz) to service_role;
grant execute on function public.consume_github_oauth_attempt(text) to service_role;
grant execute on function public.complete_github_authorization(uuid, text, text, text, text, timestamptz, timestamptz, text[]) to service_role;