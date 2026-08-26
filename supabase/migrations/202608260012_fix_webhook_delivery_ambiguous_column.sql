-- Fixes the same class of bug as 202608260011: process_github_webhook_delivery's
-- RETURNS TABLE output parameters (profile_id, connection_id) collide with real
-- column names used throughout the function body, causing every webhook
-- delivery to fail with "column reference is ambiguous" (42702). Found via
-- live webhook simulation testing. Same fix: #variable_conflict use_column.
-- External signature and return shape are unchanged.

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
#variable_conflict use_column
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

revoke all on function public.process_github_webhook_delivery(bigint, text, text, jsonb) from public, anon, authenticated;
grant execute on function public.process_github_webhook_delivery(bigint, text, text, jsonb) to service_role;
