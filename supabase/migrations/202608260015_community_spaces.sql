-- DevStacks community: spaces, posts, and moderation with provenance.
--
-- A moderation decision is recorded the same way a claim is: the action, the
-- policy version that produced it, and the individual signals that fired. That
-- makes every removal reviewable and appealable instead of arbitrary.
--
-- Posts are written through a server-only RPC so a post and the decision that
-- admitted it are always created together. A post cannot exist without the
-- verdict that let it in.

create type public.moderation_action as enum (
  'allow',
  'allow_with_notice',
  'hold_for_review',
  'block'
);

create type public.moderation_severity as enum ('none', 'low', 'medium', 'high', 'critical');

create type public.post_intent as enum (
  'help_request',
  'job_post',
  'showcase',
  'discussion',
  'hostile',
  'unknown'
);

create type public.post_visibility as enum ('published', 'held', 'blocked', 'removed');

create table public.community_spaces (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique check (slug ~ '^[a-z0-9][a-z0-9-]{1,38}$'),
  name text not null,
  description text not null,
  -- Claim categories this space is about. Expertise routing matches a member's
  -- verified claims against these, so voice is earned by evidence, not tenure.
  topic_categories text[] not null default '{}',
  -- Intents this space accepts. A help space can keep recruitment out.
  allowed_intents public.post_intent[] not null default '{}',
  is_archived boolean not null default false,
  created_at timestamptz not null default now()
);

create table public.community_posts (
  id uuid primary key default gen_random_uuid(),
  space_id uuid not null references public.community_spaces(id) on delete cascade,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  parent_post_id uuid references public.community_posts(id) on delete cascade,
  title text,
  body text not null check (char_length(body) between 1 and 20000),
  intent public.post_intent not null default 'unknown',
  visibility public.post_visibility not null default 'published',
  reply_count integer not null default 0 check (reply_count >= 0),
  created_at timestamptz not null default now(),
  edited_at timestamptz,
  -- A thread has a title; a reply has a parent. Never both, never neither.
  constraint community_posts_shape check (
    (parent_post_id is null and title is not null and char_length(trim(title)) > 0)
    or (parent_post_id is not null and title is null)
  )
);

create index community_posts_space_created_idx
  on public.community_posts (space_id, created_at desc)
  where parent_post_id is null;
create index community_posts_parent_idx on public.community_posts (parent_post_id, created_at);
create index community_posts_profile_idx on public.community_posts (profile_id, created_at desc);

create table public.moderation_decisions (
  id uuid primary key default gen_random_uuid(),
  post_id uuid not null references public.community_posts(id) on delete cascade,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  action public.moderation_action not null,
  severity public.moderation_severity not null,
  intent public.post_intent not null,
  policy_version text not null,
  rationale text not null,
  decided_by text not null default 'policy' check (decided_by in ('policy', 'moderator')),
  moderator_profile_id uuid references public.profiles(id) on delete set null,
  decided_at timestamptz not null default now(),
  -- Only a person can be the moderator on a human decision.
  constraint moderation_decisions_moderator check (
    (decided_by = 'moderator' and moderator_profile_id is not null)
    or (decided_by = 'policy' and moderator_profile_id is null)
  )
);

create index moderation_decisions_post_idx on public.moderation_decisions (post_id, decided_at desc);

create table public.moderation_signals (
  id uuid primary key default gen_random_uuid(),
  decision_id uuid not null references public.moderation_decisions(id) on delete cascade,
  kind text not null,
  severity public.moderation_severity not null,
  rule_id text not null,
  explanation text not null,
  -- Redacted upstream: a credential excerpt is never stored in full.
  excerpt text
);

create index moderation_signals_decision_idx on public.moderation_signals (decision_id);

alter table public.community_spaces enable row level security;
alter table public.community_posts enable row level security;
alter table public.moderation_decisions enable row level security;
alter table public.moderation_signals enable row level security;

-- Spaces are public reading matter.
create policy "community_spaces_select_all" on public.community_spaces
  for select to anon, authenticated using (true);

-- A published post is public. A held or blocked post is visible only to the
-- person who wrote it, so nobody is moderated in secret.
create policy "community_posts_select_published" on public.community_posts
  for select to anon, authenticated using (visibility = 'published');

create policy "community_posts_select_own" on public.community_posts
  for select to authenticated using (private.owns_profile(profile_id));

-- An author can always see why their own post was actioned.
create policy "moderation_decisions_select_own" on public.moderation_decisions
  for select to authenticated using (private.owns_profile(profile_id));

create policy "moderation_signals_select_own" on public.moderation_signals
  for select to authenticated using (
    exists (
      select 1
      from public.moderation_decisions as decision
      where decision.id = moderation_signals.decision_id
        and private.owns_profile(decision.profile_id)
    )
  );

-- Writes go through the server-only RPC below, never directly.
create or replace function public.create_community_post(
  p_profile_id uuid,
  p_space_slug text,
  p_parent_post_id uuid,
  p_title text,
  p_body text,
  p_intent public.post_intent,
  p_visibility public.post_visibility,
  p_action public.moderation_action,
  p_severity public.moderation_severity,
  p_policy_version text,
  p_rationale text,
  p_signals jsonb default '[]'::jsonb
)
returns table (post_id uuid, decision_id uuid)
language plpgsql
security definer
set search_path = ''
as $$
declare
  target_space_id uuid;
  created_post_id uuid;
  created_decision_id uuid;
begin
  select space.id into target_space_id
  from public.community_spaces as space
  where space.slug = p_space_slug and space.is_archived = false;

  if target_space_id is null then
    raise exception 'space not found or archived';
  end if;

  if p_parent_post_id is not null then
    -- A reply must belong to the same space as the thread it answers, and a
    -- reply to a reply flattens onto the thread rather than nesting forever.
    if not exists (
      select 1 from public.community_posts as parent
      where parent.id = p_parent_post_id
        and parent.space_id = target_space_id
        and parent.parent_post_id is null
        and parent.visibility = 'published'
    ) then
      raise exception 'parent post is not an open thread in this space';
    end if;
  end if;

  insert into public.community_posts (
    space_id, profile_id, parent_post_id, title, body, intent, visibility
  )
  values (
    target_space_id, p_profile_id, p_parent_post_id, p_title, p_body, p_intent, p_visibility
  )
  returning id into created_post_id;

  insert into public.moderation_decisions (
    post_id, profile_id, action, severity, intent, policy_version, rationale
  )
  values (
    created_post_id, p_profile_id, p_action, p_severity, p_intent, p_policy_version, p_rationale
  )
  returning id into created_decision_id;

  insert into public.moderation_signals (decision_id, kind, severity, rule_id, explanation, excerpt)
  select
    created_decision_id,
    signal ->> 'kind',
    (signal ->> 'severity')::public.moderation_severity,
    signal ->> 'rule_id',
    signal ->> 'explanation',
    signal ->> 'excerpt'
  from jsonb_array_elements(coalesce(p_signals, '[]'::jsonb)) as signal;

  -- Only a post that actually reached the space counts toward the thread.
  if p_parent_post_id is not null and p_visibility = 'published' then
    update public.community_posts
    set reply_count = reply_count + 1
    where id = p_parent_post_id;
  end if;

  return query select created_post_id, created_decision_id;
end;
$$;

revoke all on function public.create_community_post(
  uuid, text, uuid, text, text, public.post_intent, public.post_visibility,
  public.moderation_action, public.moderation_severity, text, text, jsonb
) from public, anon, authenticated;
grant execute on function public.create_community_post(
  uuid, text, uuid, text, text, public.post_intent, public.post_visibility,
  public.moderation_action, public.moderation_severity, text, text, jsonb
) to service_role;

-- Seed the initial spaces. Slugs are stable identifiers other systems can cite.
insert into public.community_spaces (slug, name, description, topic_categories, allowed_intents)
values
  (
    'help',
    'Help & debugging',
    'Stuck on something real. Bring the error, the versions, and what you already tried.',
    array['language.python', 'language.typescript', 'domain.distributed-systems'],
    array['help_request', 'discussion']::public.post_intent[]
  ),
  (
    'architecture',
    'Architecture & trade-offs',
    'Design decisions and the arguments against them. Strong opinions welcome, aimed at ideas.',
    array['domain.distributed-systems', 'practice.testing'],
    array['discussion', 'help_request']::public.post_intent[]
  ),
  (
    'showcase',
    'Showcase',
    'What you built and what it taught you. Evidence-backed, not press-release.',
    array[]::text[],
    array['showcase', 'discussion']::public.post_intent[]
  ),
  (
    'jobs',
    'Jobs',
    'Roles and availability. Recruiting belongs here and nowhere else.',
    array[]::text[],
    array['job_post']::public.post_intent[]
  )
on conflict (slug) do nothing;
