-- DevStacks ingestion worker leases and provider event deduplication.
-- Worker RPCs are server-only. They atomically claim/reclaim work without
-- blocking concurrent workers and preserve explicit terminal run outcomes.

alter table public.ingestion_runs
  add column attempt_count integer not null default 0 check (attempt_count >= 0),
  add column lease_owner text,
  add column lease_expires_at timestamptz;

alter table public.ingestion_runs
  add constraint ingestion_runs_lease_fields_check check (
    (status = 'running' and lease_owner is not null and lease_expires_at is not null)
    or (status <> 'running' and lease_owner is null and lease_expires_at is null)
  );

create index ingestion_runs_claimable_idx
  on public.ingestion_runs (created_at)
  where status = 'queued' or (status = 'running' and lease_expires_at is not null);

create table public.provider_events (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  connection_id uuid not null references public.source_connections(id) on delete cascade,
  provider_event_id text not null,
  event_type text not null,
  payload jsonb not null default '{}'::jsonb,
  received_at timestamptz not null default now(),
  ingestion_run_id uuid references public.ingestion_runs(id) on delete set null,
  processed_at timestamptz,
  unique (connection_id, provider_event_id)
);

create index provider_events_profile_id_received_at_idx
  on public.provider_events (profile_id, received_at desc);
create index provider_events_ingestion_run_id_idx
  on public.provider_events (ingestion_run_id);

alter table public.provider_events enable row level security;

create policy "provider_events_select_own" on public.provider_events
  for select to authenticated
  using (private.owns_profile(profile_id));

create or replace function public.record_provider_event(
  p_profile_id uuid,
  p_connection_id uuid,
  p_provider_event_id text,
  p_event_type text,
  p_payload jsonb default '{}'::jsonb
)
returns public.provider_events
language plpgsql
security definer
set search_path = ''
as $$
declare
  recorded_event public.provider_events;
begin
  if char_length(trim(p_provider_event_id)) = 0 or char_length(trim(p_event_type)) = 0 then
    raise exception 'provider event id and type are required';
  end if;
  if not exists (
    select 1
    from public.source_connections
    where id = p_connection_id
      and profile_id = p_profile_id
  ) then
    raise exception 'source connection does not belong to the profile';
  end if;

  insert into public.provider_events (
    profile_id,
    connection_id,
    provider_event_id,
    event_type,
    payload
  )
  values (
    p_profile_id,
    p_connection_id,
    p_provider_event_id,
    p_event_type,
    p_payload
  )
  on conflict (connection_id, provider_event_id) do nothing
  returning * into recorded_event;

  if not found then
    select * into recorded_event
    from public.provider_events
    where connection_id = p_connection_id
      and provider_event_id = p_provider_event_id;
  end if;

  return recorded_event;
end;
$$;

create or replace function public.claim_ingestion_run(
  p_worker_id text,
  p_lease_seconds integer default 60
)
returns public.ingestion_runs
language plpgsql
security definer
set search_path = ''
as $$
declare
  claimed_run public.ingestion_runs;
begin
  if char_length(trim(p_worker_id)) = 0 then
    raise exception 'worker id is required';
  end if;
  if p_lease_seconds < 1 or p_lease_seconds > 3600 then
    raise exception 'lease seconds must be between 1 and 3600';
  end if;

  with candidate as (
    select id
    from public.ingestion_runs
    where status = 'queued'
       or (status = 'running' and lease_expires_at <= now())
    order by created_at
    for update skip locked
    limit 1
  )
  update public.ingestion_runs as run
  set status = 'running',
      started_at = coalesce(run.started_at, now()),
      attempt_count = run.attempt_count + 1,
      lease_owner = p_worker_id,
      lease_expires_at = now() + make_interval(secs => p_lease_seconds),
      error_summary = null
  from candidate
  where run.id = candidate.id
  returning run.* into claimed_run;

  if not found then
    return null;
  end if;

  return claimed_run;
end;
$$;

create or replace function public.complete_ingestion_run(
  p_run_id uuid,
  p_worker_id text,
  p_status text,
  p_error_summary text default null
)
returns public.ingestion_runs
language plpgsql
security definer
set search_path = ''
as $$
declare
  completed_run public.ingestion_runs;
begin
  if p_status not in ('succeeded', 'partial', 'failed', 'no_op') then
    raise exception 'ingestion completion status is invalid';
  end if;

  update public.ingestion_runs
  set status = p_status,
      completed_at = now(),
      error_summary = p_error_summary,
      lease_owner = null,
      lease_expires_at = null
  where id = p_run_id
    and status = 'running'
    and lease_owner = p_worker_id
    and lease_expires_at > now()
  returning * into completed_run;

  if not found then
    raise exception 'ingestion run is not actively leased by this worker';
  end if;

  return completed_run;
end;
$$;

revoke all on function public.claim_ingestion_run(text, integer) from public, anon, authenticated;
revoke all on function public.complete_ingestion_run(uuid, text, text, text) from public, anon, authenticated;
revoke all on function public.record_provider_event(uuid, uuid, text, text, jsonb) from public, anon, authenticated;
grant execute on function public.claim_ingestion_run(text, integer) to service_role;
grant execute on function public.complete_ingestion_run(uuid, text, text, text) to service_role;
grant execute on function public.record_provider_event(uuid, uuid, text, text, jsonb) to service_role;
