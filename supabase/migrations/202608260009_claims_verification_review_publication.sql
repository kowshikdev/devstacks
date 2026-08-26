-- GH-005/GH-006: structured candidate claims, first-class claim revisions with
-- evidence links, verifier/review decisions, provenance-guarded publication,
-- and lease-based agent-run queueing (mirrors 202608260003_ingestion_job_leases.sql).
-- All writes are append-only and tenant-scoped; state-machine enforcement for
-- verification/review/publication transitions lives in the domain layer, not here.

alter table public.agent_runs
  add column source_artifact_id uuid references public.source_artifacts(id) on delete set null,
  add column evidence_version_id uuid references public.evidence_versions(id) on delete set null,
  add column idempotency_key text,
  add column attempt_count integer not null default 0 check (attempt_count >= 0),
  add column lease_owner text,
  add column lease_expires_at timestamptz,
  add column error_summary text;

alter table public.agent_runs
  add constraint agent_runs_lease_fields_check check (
    (status = 'running' and lease_owner is not null and lease_expires_at is not null)
    or (status <> 'running' and lease_owner is null and lease_expires_at is null)
  );

alter table public.agent_runs
  add constraint agent_runs_idempotency_key_unique unique nulls not distinct (profile_id, idempotency_key);

create index agent_runs_claimable_idx
  on public.agent_runs (created_at)
  where status = 'queued' or (status = 'running' and lease_expires_at is not null);

-- Claim intake: creates a claim (if none given) and its next immutable revision,
-- with evidence links validated against the profile's own evidence versions.
create or replace function public.create_claim_revision(
  p_profile_id uuid,
  p_claim_id uuid,
  p_category text,
  p_statement text,
  p_valid_from timestamptz,
  p_valid_until timestamptz,
  p_evidence_links jsonb
)
returns table (
  claim_id uuid,
  claim_revision_id uuid,
  revision_number integer
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  target_claim_id uuid;
  next_revision_number integer;
  new_revision_id uuid;
  link jsonb;
  link_evidence_version_id uuid;
  link_relation text;
begin
  if char_length(trim(p_category)) = 0 or char_length(trim(p_statement)) = 0 then
    raise exception 'claim category and statement are required';
  end if;
  if p_evidence_links is null or jsonb_typeof(p_evidence_links) <> 'array' or jsonb_array_length(p_evidence_links) = 0 then
    raise exception 'at least one evidence link is required';
  end if;

  if p_claim_id is null then
    insert into public.claims (profile_id, category)
    values (p_profile_id, p_category)
    returning id into target_claim_id;
  else
    if not exists (
      select 1 from public.claims
      where id = p_claim_id and profile_id = p_profile_id
    ) then
      raise exception 'claim does not belong to the profile';
    end if;
    target_claim_id := p_claim_id;
  end if;

  select coalesce(max(revision.revision_number), 0) + 1
  into next_revision_number
  from public.claim_revisions as revision
  where revision.claim_id = target_claim_id;

  insert into public.claim_revisions (
    claim_id,
    profile_id,
    revision_number,
    statement,
    valid_from,
    valid_until
  )
  values (
    target_claim_id,
    p_profile_id,
    next_revision_number,
    p_statement,
    p_valid_from,
    p_valid_until
  )
  returning id into new_revision_id;

  for link in select * from jsonb_array_elements(p_evidence_links)
  loop
    link_evidence_version_id := (link ->> 'evidence_version_id')::uuid;
    link_relation := link ->> 'relation';
    if link_relation not in ('supports', 'contradicts', 'context') then
      raise exception 'evidence link relation is invalid';
    end if;
    if not exists (
      select 1 from public.evidence_versions
      where id = link_evidence_version_id and profile_id = p_profile_id
    ) then
      raise exception 'evidence version does not belong to the profile';
    end if;
    insert into public.claim_evidence_links (claim_revision_id, evidence_version_id, relation)
    values (new_revision_id, link_evidence_version_id, link_relation::public.evidence_relation);
  end loop;

  return query select target_claim_id, new_revision_id, next_revision_number;
end;
$$;

-- Dumb append. The domain layer calls validate_transition() against
-- VERIFICATION_TRANSITIONS before invoking this RPC.
create or replace function public.record_verification_decision(
  p_profile_id uuid,
  p_claim_revision_id uuid,
  p_status public.verification_status,
  p_verifier_score numeric,
  p_agent_run_id uuid,
  p_rationale text
)
returns public.verification_decisions
language plpgsql
security definer
set search_path = ''
as $$
declare
  decision public.verification_decisions;
begin
  if not exists (
    select 1 from public.claim_revisions
    where id = p_claim_revision_id and profile_id = p_profile_id
  ) then
    raise exception 'claim revision does not belong to the profile';
  end if;
  if p_agent_run_id is not null and not exists (
    select 1 from public.agent_runs
    where id = p_agent_run_id and profile_id = p_profile_id
  ) then
    raise exception 'agent run does not belong to the profile';
  end if;

  insert into public.verification_decisions (
    claim_revision_id,
    profile_id,
    status,
    verifier_score,
    agent_run_id,
    rationale
  )
  values (
    p_claim_revision_id,
    p_profile_id,
    p_status,
    p_verifier_score,
    p_agent_run_id,
    p_rationale
  )
  returning * into decision;

  return decision;
end;
$$;

-- Dumb append. Review is a human, deterministic action — the domain layer
-- calls validate_transition() against REVIEW_TRANSITIONS before invoking this.
create or replace function public.record_review_decision(
  p_profile_id uuid,
  p_claim_revision_id uuid,
  p_status public.review_status,
  p_actor_user_id uuid,
  p_note text
)
returns public.review_decisions
language plpgsql
security definer
set search_path = ''
as $$
declare
  decision public.review_decisions;
begin
  if p_actor_user_id is null then
    raise exception 'review actor is required';
  end if;
  if not exists (
    select 1 from public.claim_revisions
    where id = p_claim_revision_id and profile_id = p_profile_id
  ) then
    raise exception 'claim revision does not belong to the profile';
  end if;

  insert into public.review_decisions (
    claim_revision_id,
    profile_id,
    status,
    actor_user_id,
    note
  )
  values (
    p_claim_revision_id,
    p_profile_id,
    p_status,
    p_actor_user_id,
    p_note
  )
  returning * into decision;

  return decision;
end;
$$;

-- Scoped reads used by the domain layer to fetch current state before
-- validating a transition. Absence of any decision row is the caller's
-- (Python-side) signal for the default UNVERIFIED/PENDING starting state.
create or replace function public.get_latest_verification_status(
  p_profile_id uuid,
  p_claim_revision_id uuid
)
returns public.verification_status
language sql
stable
security definer
set search_path = ''
as $$
  select decision.status
  from public.verification_decisions as decision
  where decision.claim_revision_id = p_claim_revision_id
    and decision.profile_id = p_profile_id
  order by decision.decided_at desc
  limit 1;
$$;

create or replace function public.get_latest_review_status(
  p_profile_id uuid,
  p_claim_revision_id uuid
)
returns public.review_status
language sql
stable
security definer
set search_path = ''
as $$
  select decision.status
  from public.review_decisions as decision
  where decision.claim_revision_id = p_claim_revision_id
    and decision.profile_id = p_profile_id
  order by decision.decided_at desc
  limit 1;
$$;

-- Read-only evidence lookup exposed to agent tools (extractor/verifier). Never
-- exposes connector tokens or anything beyond the evidence version's own
-- normalized payload and provenance metadata.
create or replace function public.get_evidence_version(
  p_profile_id uuid,
  p_evidence_version_id uuid
)
returns table (
  evidence_version_id uuid,
  source_artifact_id uuid,
  source_type text,
  source_ref text,
  canonical_payload jsonb,
  content_hash text,
  assurance_class text,
  validity public.evidence_validity,
  observed_at timestamptz
)
language sql
stable
security definer
set search_path = ''
as $$
  select
    version.id,
    version.source_artifact_id,
    artifact.source_type,
    artifact.source_ref,
    version.canonical_payload,
    version.content_hash,
    version.assurance_class,
    version.validity,
    version.observed_at
  from public.evidence_versions as version
  join public.source_artifacts as artifact on artifact.id = version.source_artifact_id
  where version.id = p_evidence_version_id
    and version.profile_id = p_profile_id;
$$;

-- Bundles everything the publish flow needs to build a PublicationRequest in
-- one round trip: latest verification/review decision ids and statuses, plus
-- the claim revision's evidence provenance sets.
create or replace function public.get_claim_revision_publication_context(
  p_profile_id uuid,
  p_claim_revision_id uuid
)
returns table (
  verification_decision_id uuid,
  verification_status public.verification_status,
  verifier_score numeric,
  review_decision_id uuid,
  review_status public.review_status,
  evidence_version_ids uuid[],
  evidence_validity public.evidence_validity[],
  source_artifact_ids uuid[]
)
language sql
stable
security definer
set search_path = ''
as $$
  with latest_verification as (
    select decision.id, decision.status, decision.verifier_score
    from public.verification_decisions as decision
    where decision.claim_revision_id = p_claim_revision_id
      and decision.profile_id = p_profile_id
    order by decision.decided_at desc
    limit 1
  ),
  latest_review as (
    select decision.id, decision.status
    from public.review_decisions as decision
    where decision.claim_revision_id = p_claim_revision_id
      and decision.profile_id = p_profile_id
    order by decision.decided_at desc
    limit 1
  ),
  evidence as (
    select
      array_agg(distinct version.id) as evidence_version_ids,
      array_agg(distinct version.validity) as evidence_validity,
      array_agg(distinct version.source_artifact_id) as source_artifact_ids
    from public.claim_evidence_links as link
    join public.evidence_versions as version on version.id = link.evidence_version_id
    where link.claim_revision_id = p_claim_revision_id
      and version.profile_id = p_profile_id
  )
  select
    latest_verification.id,
    latest_verification.status,
    latest_verification.verifier_score,
    latest_review.id,
    latest_review.status,
    evidence.evidence_version_ids,
    evidence.evidence_validity,
    evidence.source_artifact_ids
  from evidence
  left join latest_verification on true
  left join latest_review on true;
$$;

-- Defense-in-depth: re-derives that the referenced decisions actually confirm
-- verified/approved rather than trusting caller-supplied foreign keys blindly.
create or replace function public.record_publication(
  p_profile_id uuid,
  p_claim_revision_id uuid,
  p_verification_decision_id uuid,
  p_review_decision_id uuid,
  p_policy_version_id uuid,
  p_status public.publication_status,
  p_published_at timestamptz default null,
  p_withdrawn_at timestamptz default null
)
returns public.publications
language plpgsql
security definer
set search_path = ''
as $$
declare
  publication public.publications;
  verification_ok boolean;
  review_ok boolean;
begin
  if not exists (
    select 1 from public.claim_revisions
    where id = p_claim_revision_id and profile_id = p_profile_id
  ) then
    raise exception 'claim revision does not belong to the profile';
  end if;

  select exists (
    select 1 from public.verification_decisions
    where id = p_verification_decision_id
      and profile_id = p_profile_id
      and claim_revision_id = p_claim_revision_id
      and status = 'verified'
  ) into verification_ok;
  if not verification_ok then
    raise exception 'verification decision does not confirm this claim revision as verified';
  end if;

  if p_review_decision_id is not null then
    select exists (
      select 1 from public.review_decisions
      where id = p_review_decision_id
        and profile_id = p_profile_id
        and claim_revision_id = p_claim_revision_id
        and status = 'approved'
    ) into review_ok;
    if not review_ok then
      raise exception 'review decision does not confirm this claim revision as approved';
    end if;
  end if;

  if p_status = 'published' and p_published_at is null then
    raise exception 'published status requires a published timestamp';
  end if;
  if p_status = 'withdrawn' and p_withdrawn_at is null then
    raise exception 'withdrawn status requires a withdrawn timestamp';
  end if;

  insert into public.publications (
    claim_revision_id,
    profile_id,
    verification_decision_id,
    review_decision_id,
    policy_version_id,
    status,
    published_at,
    withdrawn_at
  )
  values (
    p_claim_revision_id,
    p_profile_id,
    p_verification_decision_id,
    p_review_decision_id,
    p_policy_version_id,
    p_status,
    p_published_at,
    p_withdrawn_at
  )
  returning * into publication;

  return publication;
end;
$$;

-- Joined read for the review dashboard: pending claim revisions with their
-- latest verification/review/freshness state and evidence explanations.
create or replace function public.list_pending_claim_revisions(
  p_profile_id uuid
)
returns table (
  claim_revision_id uuid,
  claim_id uuid,
  category text,
  statement text,
  revision_number integer,
  created_at timestamptz,
  latest_verification_status public.verification_status,
  latest_verifier_score numeric,
  latest_review_status public.review_status,
  latest_freshness_status public.evidence_validity,
  evidence jsonb
)
language sql
stable
security definer
set search_path = ''
as $$
  with latest_verification as (
    select distinct on (decision.claim_revision_id)
      decision.claim_revision_id, decision.status, decision.verifier_score
    from public.verification_decisions as decision
    where decision.profile_id = p_profile_id
    order by decision.claim_revision_id, decision.decided_at desc
  ),
  latest_review as (
    select distinct on (decision.claim_revision_id)
      decision.claim_revision_id, decision.status
    from public.review_decisions as decision
    where decision.profile_id = p_profile_id
    order by decision.claim_revision_id, decision.decided_at desc
  ),
  latest_freshness as (
    select distinct on (assessment.claim_revision_id)
      assessment.claim_revision_id, assessment.status
    from public.freshness_assessments as assessment
    where assessment.profile_id = p_profile_id
    order by assessment.claim_revision_id, assessment.assessed_at desc
  ),
  evidence_summary as (
    select
      link.claim_revision_id,
      jsonb_agg(
        jsonb_build_object(
          'evidence_version_id', link.evidence_version_id,
          'relation', link.relation,
          'source_type', artifact.source_type,
          'source_ref', artifact.source_ref,
          'assurance_class', version.assurance_class,
          'validity', version.validity
        )
      ) as evidence
    from public.claim_evidence_links as link
    join public.evidence_versions as version on version.id = link.evidence_version_id
    join public.source_artifacts as artifact on artifact.id = version.source_artifact_id
    where version.profile_id = p_profile_id
    group by link.claim_revision_id
  )
  select
    revision.id,
    revision.claim_id,
    claim.category,
    revision.statement,
    revision.revision_number,
    revision.created_at,
    latest_verification.status,
    latest_verification.verifier_score,
    latest_review.status,
    latest_freshness.status,
    coalesce(evidence_summary.evidence, '[]'::jsonb)
  from public.claim_revisions as revision
  join public.claims as claim on claim.id = revision.claim_id
  left join latest_verification on latest_verification.claim_revision_id = revision.id
  left join latest_review on latest_review.claim_revision_id = revision.id
  left join latest_freshness on latest_freshness.claim_revision_id = revision.id
  left join evidence_summary on evidence_summary.claim_revision_id = revision.id
  where revision.profile_id = p_profile_id
    and (latest_review.status is null or latest_review.status = 'pending');
$$;

-- Scoped read used by the reviewer-edit flow to carry forward a prior
-- revision's evidence links onto its immutable successor.
create or replace function public.get_claim_revision_evidence_links(
  p_profile_id uuid,
  p_claim_revision_id uuid
)
returns table (
  evidence_version_id uuid,
  relation public.evidence_relation
)
language sql
stable
security definer
set search_path = ''
as $$
  select link.evidence_version_id, link.relation
  from public.claim_evidence_links as link
  join public.claim_revisions as revision on revision.id = link.claim_revision_id
  where revision.id = p_claim_revision_id
    and revision.profile_id = p_profile_id;
$$;

-- Cheap, synchronous queue write. The LLM extraction itself runs later,
-- out-of-band, in the leased worker below.
create or replace function public.enqueue_claim_agent_run(
  p_profile_id uuid,
  p_source_artifact_id uuid,
  p_evidence_version_id uuid,
  p_idempotency_key text
)
returns public.agent_runs
language plpgsql
security definer
set search_path = ''
as $$
declare
  run public.agent_runs;
begin
  if char_length(trim(p_idempotency_key)) = 0 then
    raise exception 'agent run idempotency key is required';
  end if;
  if not exists (
    select 1 from public.evidence_versions
    where id = p_evidence_version_id
      and profile_id = p_profile_id
      and source_artifact_id = p_source_artifact_id
  ) then
    raise exception 'evidence version does not belong to the profile or artifact';
  end if;

  insert into public.agent_runs (
    profile_id,
    workflow_name,
    status,
    source_artifact_id,
    evidence_version_id,
    idempotency_key
  )
  values (
    p_profile_id,
    'claim_extraction',
    'queued',
    p_source_artifact_id,
    p_evidence_version_id,
    p_idempotency_key
  )
  on conflict (profile_id, idempotency_key) do update
  set id = public.agent_runs.id
  returning * into run;

  return run;
end;
$$;

-- Lease claim/complete pair, mirroring claim_ingestion_run/complete_ingestion_run
-- in 202608260003_ingestion_job_leases.sql exactly, sized for LLM latency by the
-- caller via p_lease_seconds rather than a shorter hardcoded ingestion default.
create or replace function public.claim_agent_run(
  p_worker_id text,
  p_lease_seconds integer default 300
)
returns public.agent_runs
language plpgsql
security definer
set search_path = ''
as $$
declare
  claimed_run public.agent_runs;
begin
  if char_length(trim(p_worker_id)) = 0 then
    raise exception 'worker id is required';
  end if;
  if p_lease_seconds < 1 or p_lease_seconds > 3600 then
    raise exception 'lease seconds must be between 1 and 3600';
  end if;

  with candidate as (
    select id
    from public.agent_runs
    where status = 'queued'
       or (status = 'running' and lease_expires_at <= now())
    order by created_at
    for update skip locked
    limit 1
  )
  update public.agent_runs as run
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

create or replace function public.complete_agent_run(
  p_run_id uuid,
  p_worker_id text,
  p_status text,
  p_error_summary text default null
)
returns public.agent_runs
language plpgsql
security definer
set search_path = ''
as $$
declare
  completed_run public.agent_runs;
begin
  if p_status not in ('succeeded', 'failed', 'interrupted') then
    raise exception 'agent run completion status is invalid';
  end if;

  update public.agent_runs
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
    raise exception 'agent run is not actively leased by this worker';
  end if;

  return completed_run;
end;
$$;

create or replace function public.get_agent_run(
  p_profile_id uuid,
  p_run_id uuid
)
returns public.agent_runs
language sql
stable
security definer
set search_path = ''
as $$
  select * from public.agent_runs
  where id = p_run_id and profile_id = p_profile_id;
$$;

revoke all on function public.create_claim_revision(uuid, uuid, text, text, timestamptz, timestamptz, jsonb) from public, anon, authenticated;
revoke all on function public.record_verification_decision(uuid, uuid, public.verification_status, numeric, uuid, text) from public, anon, authenticated;
revoke all on function public.record_review_decision(uuid, uuid, public.review_status, uuid, text) from public, anon, authenticated;
revoke all on function public.record_publication(uuid, uuid, uuid, uuid, uuid, public.publication_status, timestamptz, timestamptz) from public, anon, authenticated;
revoke all on function public.list_pending_claim_revisions(uuid) from public, anon, authenticated;
revoke all on function public.get_claim_revision_evidence_links(uuid, uuid) from public, anon, authenticated;
revoke all on function public.get_latest_verification_status(uuid, uuid) from public, anon, authenticated;
revoke all on function public.get_latest_review_status(uuid, uuid) from public, anon, authenticated;
revoke all on function public.get_claim_revision_publication_context(uuid, uuid) from public, anon, authenticated;
revoke all on function public.get_evidence_version(uuid, uuid) from public, anon, authenticated;
revoke all on function public.enqueue_claim_agent_run(uuid, uuid, uuid, text) from public, anon, authenticated;
revoke all on function public.claim_agent_run(text, integer) from public, anon, authenticated;
revoke all on function public.complete_agent_run(uuid, text, text, text) from public, anon, authenticated;
revoke all on function public.get_agent_run(uuid, uuid) from public, anon, authenticated;

grant execute on function public.create_claim_revision(uuid, uuid, text, text, timestamptz, timestamptz, jsonb) to service_role;
grant execute on function public.record_verification_decision(uuid, uuid, public.verification_status, numeric, uuid, text) to service_role;
grant execute on function public.record_review_decision(uuid, uuid, public.review_status, uuid, text) to service_role;
grant execute on function public.record_publication(uuid, uuid, uuid, uuid, uuid, public.publication_status, timestamptz, timestamptz) to service_role;
grant execute on function public.list_pending_claim_revisions(uuid) to service_role;
grant execute on function public.get_claim_revision_evidence_links(uuid, uuid) to service_role;
grant execute on function public.get_latest_verification_status(uuid, uuid) to service_role;
grant execute on function public.get_latest_review_status(uuid, uuid) to service_role;
grant execute on function public.get_claim_revision_publication_context(uuid, uuid) to service_role;
grant execute on function public.get_evidence_version(uuid, uuid) to service_role;
grant execute on function public.enqueue_claim_agent_run(uuid, uuid, uuid, text) to service_role;
grant execute on function public.claim_agent_run(text, integer) to service_role;
grant execute on function public.complete_agent_run(uuid, text, text, text) to service_role;
grant execute on function public.get_agent_run(uuid, uuid) to service_role;
