create table public.github_webhook_subscriptions (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  connection_id uuid not null references public.source_connections(id) on delete cascade,
  github_repository_id bigint not null,
  github_hook_id bigint not null unique,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (connection_id, github_repository_id)
);

create index github_webhook_subscriptions_hook_idx
  on public.github_webhook_subscriptions (github_hook_id)
  where active;

alter table public.github_webhook_subscriptions enable row level security;

create or replace function public.register_github_webhook_subscription(
  p_profile_id uuid,
  p_connection_id uuid,
  p_github_repository_id bigint,
  p_github_hook_id bigint
)
returns public.github_webhook_subscriptions
language plpgsql
security definer
set search_path = ''
as $$
declare
  subscription public.github_webhook_subscriptions;
begin
  if p_github_repository_id < 1 or p_github_hook_id < 1 then
    raise exception 'github webhook identifiers are invalid';
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

  insert into public.github_webhook_subscriptions (
    profile_id,
    connection_id,
    github_repository_id,
    github_hook_id,
    active,
    updated_at
  )
  values (
    p_profile_id,
    p_connection_id,
    p_github_repository_id,
    p_github_hook_id,
    true,
    now()
  )
  on conflict (connection_id, github_repository_id) do update
  set github_hook_id = excluded.github_hook_id,
      active = true,
      updated_at = excluded.updated_at
  returning * into subscription;

  return subscription;
end;
$$;

create or replace function public.process_github_webhook_delivery(
  p_github_hook_id bigint,
  p_provider_event_id text,
  p_event_type text,
  p_payload jsonb default '{}'::jsonb
)
returns table (
  profile_id uuid,
  connection_id uuid,
  ingestion_run_id uuid,
  is_duplicate boolean
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  subscription public.github_webhook_subscriptions;
  provider_event public.provider_events;
  ingestion_run public.ingestion_runs;
  delivery_exists boolean := false;
begin
  if p_github_hook_id < 1
    or char_length(trim(p_provider_event_id)) = 0
    or char_length(trim(p_event_type)) = 0 then
    raise exception 'github webhook delivery parameters are invalid';
  end if;

  select * into subscription
  from public.github_webhook_subscriptions
  where github_hook_id = p_github_hook_id
    and active = true;
  if not found then
    return;
  end if;

  insert into public.provider_events (
    profile_id,
    connection_id,
    provider_event_id,
    event_type,
    payload
  )
  values (
    subscription.profile_id,
    subscription.connection_id,
    p_provider_event_id,
    p_event_type,
    p_payload
  )
  on conflict (connection_id, provider_event_id) do nothing
  returning * into provider_event;

  if not found then
    delivery_exists := true;
  end if;

  if p_event_type in ('push', 'pull_request', 'release') then
    insert into public.ingestion_runs (
      profile_id,
      connection_id,
      trigger_type,
      status,
      idempotency_key
    )
    values (
      subscription.profile_id,
      subscription.connection_id,
      'webhook',
      'queued',
      'github-webhook:' || p_provider_event_id
    )
    on conflict (profile_id, idempotency_key) do update
    set id = public.ingestion_runs.id
    returning * into ingestion_run;
  end if;

  return query select
    subscription.profile_id,
    subscription.connection_id,
    ingestion_run.id,
    delivery_exists;
end;
$$;

revoke all on function public.register_github_webhook_subscription(uuid, uuid, bigint, bigint) from public, anon, authenticated;
revoke all on function public.process_github_webhook_delivery(bigint, text, text, jsonb) from public, anon, authenticated;
grant execute on function public.register_github_webhook_subscription(uuid, uuid, bigint, bigint) to service_role;
grant execute on function public.process_github_webhook_delivery(bigint, text, text, jsonb) to service_role;