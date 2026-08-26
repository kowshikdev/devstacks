-- DevStacks core evidence graph.
-- This migration creates append-only provenance records. Client access remains
-- denied by RLS until FOUND-002 adds tenant-aware policies and repositories.

create extension if not exists pgcrypto;

create type public.evidence_validity as enum (
  'current', 'stale', 'unavailable', 'invalid', 'superseded'
);

create type public.verification_status as enum (
  'unverified', 'verified', 'ambiguous', 'unsupported', 'contradicted'
);

create type public.review_status as enum (
  'pending', 'approved', 'rejected'
);

create type public.publication_status as enum (
  'unpublished', 'published', 'withdrawn'
);

create type public.evidence_relation as enum ('supports', 'contradicts', 'context');

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  handle text not null unique,
  display_name text,
  is_public boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint profiles_handle_format check (handle ~ '^[a-z0-9][a-z0-9-]{2,38}$')
);

create table public.source_connections (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  platform text not null check (platform in ('github', 'linkedin', 'leetcode', 'hackerrank')),
  external_subject text,
  connection_status text not null default 'pending'
    check (connection_status in ('pending', 'active', 'degraded', 'revoked', 'disconnected')),
  connected_at timestamptz,
  last_synced_at timestamptz,
  created_at timestamptz not null default now(),
  unique (profile_id, platform, external_subject)
);

create table public.source_subjects (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  connection_id uuid not null references public.source_connections(id) on delete cascade,
  provider_subject_id text not null,
  provider_login text,
  observed_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique (connection_id, provider_subject_id)
);

create table public.identity_bindings (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  source_subject_id uuid not null references public.source_subjects(id) on delete restrict,
  assurance_class text not null,
  status text not null check (status in ('pending', 'confirmed', 'ambiguous', 'rejected')),
  confirmed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (profile_id, source_subject_id)
);

create table public.ingestion_runs (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  connection_id uuid references public.source_connections(id) on delete set null,
  trigger_type text not null check (trigger_type in ('manual', 'webhook', 'scheduled')),
  status text not null check (status in ('queued', 'running', 'succeeded', 'partial', 'failed', 'no_op')),
  idempotency_key text,
  started_at timestamptz,
  completed_at timestamptz,
  error_summary text,
  created_at timestamptz not null default now(),
  unique nulls not distinct (profile_id, idempotency_key)
);

create table public.source_artifacts (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  connection_id uuid references public.source_connections(id) on delete set null,
  source_type text not null,
  source_ref text not null,
  acquired_at timestamptz not null default now(),
  observed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (profile_id, source_type, source_ref)
);

create table public.evidence_versions (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  source_artifact_id uuid not null references public.source_artifacts(id) on delete restrict,
  version_number integer not null check (version_number > 0),
  canonical_payload jsonb not null,
  content_hash text not null check (char_length(content_hash) >= 32),
  connector_version text not null,
  assurance_class text not null,
  validity public.evidence_validity not null default 'current',
  fetched_at timestamptz not null default now(),
  observed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (source_artifact_id, version_number),
  unique (source_artifact_id, content_hash)
);

create table public.claims (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  category text not null,
  created_at timestamptz not null default now()
);

create table public.claim_revisions (
  id uuid primary key default gen_random_uuid(),
  claim_id uuid not null references public.claims(id) on delete restrict,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  revision_number integer not null check (revision_number > 0),
  statement text not null check (char_length(trim(statement)) > 0),
  valid_from timestamptz,
  valid_until timestamptz,
  created_at timestamptz not null default now(),
  constraint claim_revisions_valid_interval check (valid_until is null or valid_from is null or valid_until >= valid_from),
  unique (claim_id, revision_number)
);

create table public.claim_evidence_links (
  claim_revision_id uuid not null references public.claim_revisions(id) on delete restrict,
  evidence_version_id uuid not null references public.evidence_versions(id) on delete restrict,
  relation public.evidence_relation not null,
  created_at timestamptz not null default now(),
  primary key (claim_revision_id, evidence_version_id)
);

create table public.agent_runs (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  workflow_name text not null,
  model_identifier text,
  prompt_version text,
  ruleset_version text,
  schema_version text,
  status text not null check (status in ('queued', 'running', 'succeeded', 'failed', 'interrupted')),
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.verification_decisions (
  id uuid primary key default gen_random_uuid(),
  claim_revision_id uuid not null references public.claim_revisions(id) on delete restrict,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  status public.verification_status not null,
  verifier_score numeric(4, 3) check (verifier_score between 0 and 1),
  agent_run_id uuid references public.agent_runs(id) on delete set null,
  decided_at timestamptz not null default now(),
  rationale text
);

create table public.review_decisions (
  id uuid primary key default gen_random_uuid(),
  claim_revision_id uuid not null references public.claim_revisions(id) on delete restrict,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  status public.review_status not null,
  actor_user_id uuid not null references auth.users(id) on delete restrict,
  note text,
  decided_at timestamptz not null default now()
);

create table public.policy_versions (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  version text not null,
  policy jsonb not null,
  created_at timestamptz not null default now(),
  unique (profile_id, version)
);

create table public.publications (
  id uuid primary key default gen_random_uuid(),
  claim_revision_id uuid not null references public.claim_revisions(id) on delete restrict,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  verification_decision_id uuid not null references public.verification_decisions(id) on delete restrict,
  review_decision_id uuid references public.review_decisions(id) on delete restrict,
  policy_version_id uuid references public.policy_versions(id) on delete restrict,
  status public.publication_status not null default 'unpublished',
  published_at timestamptz,
  withdrawn_at timestamptz,
  created_at timestamptz not null default now(),
  constraint publications_timestamps check (
    (status = 'published' and published_at is not null)
    or (status = 'withdrawn' and withdrawn_at is not null)
    or status = 'unpublished'
  )
);

create table public.freshness_assessments (
  id uuid primary key default gen_random_uuid(),
  claim_revision_id uuid not null references public.claim_revisions(id) on delete restrict,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  status public.evidence_validity not null,
  reason_code text not null,
  assessed_at timestamptz not null default now(),
  recheck_after timestamptz
);

create table public.audit_events (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  actor_user_id uuid references auth.users(id) on delete set null,
  event_type text not null,
  entity_type text not null,
  entity_id uuid not null,
  idempotency_key text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique nulls not distinct (profile_id, idempotency_key)
);

create index source_connections_profile_id_idx on public.source_connections (profile_id);
create index source_subjects_profile_id_idx on public.source_subjects (profile_id);
create index source_subjects_connection_id_idx on public.source_subjects (connection_id);
create index identity_bindings_profile_id_idx on public.identity_bindings (profile_id);
create index identity_bindings_source_subject_id_idx on public.identity_bindings (source_subject_id);
create index ingestion_runs_profile_id_created_at_idx on public.ingestion_runs (profile_id, created_at desc);
create index ingestion_runs_connection_id_idx on public.ingestion_runs (connection_id);
create index source_artifacts_profile_id_idx on public.source_artifacts (profile_id);
create index source_artifacts_connection_id_idx on public.source_artifacts (connection_id);
create index evidence_versions_profile_id_idx on public.evidence_versions (profile_id);
create index evidence_versions_source_artifact_id_idx on public.evidence_versions (source_artifact_id);
create index claims_profile_id_idx on public.claims (profile_id);
create index claim_revisions_claim_id_idx on public.claim_revisions (claim_id);
create index claim_revisions_profile_id_idx on public.claim_revisions (profile_id);
create index claim_evidence_links_evidence_version_id_idx on public.claim_evidence_links (evidence_version_id);
create index agent_runs_profile_id_idx on public.agent_runs (profile_id);
create index verification_decisions_claim_revision_id_idx on public.verification_decisions (claim_revision_id);
create index verification_decisions_profile_id_idx on public.verification_decisions (profile_id);
create index review_decisions_claim_revision_id_idx on public.review_decisions (claim_revision_id);
create index review_decisions_profile_id_idx on public.review_decisions (profile_id);
create index policy_versions_profile_id_idx on public.policy_versions (profile_id);
create index publications_claim_revision_id_idx on public.publications (claim_revision_id);
create index publications_profile_id_status_idx on public.publications (profile_id, status);
create index freshness_assessments_claim_revision_id_idx on public.freshness_assessments (claim_revision_id);
create index freshness_assessments_profile_id_idx on public.freshness_assessments (profile_id);
create index audit_events_profile_id_created_at_idx on public.audit_events (profile_id, created_at desc);

alter table public.profiles enable row level security;
alter table public.source_connections enable row level security;
alter table public.source_subjects enable row level security;
alter table public.identity_bindings enable row level security;
alter table public.ingestion_runs enable row level security;
alter table public.source_artifacts enable row level security;
alter table public.evidence_versions enable row level security;
alter table public.claims enable row level security;
alter table public.claim_revisions enable row level security;
alter table public.claim_evidence_links enable row level security;
alter table public.agent_runs enable row level security;
alter table public.verification_decisions enable row level security;
alter table public.review_decisions enable row level security;
alter table public.policy_versions enable row level security;
alter table public.publications enable row level security;
alter table public.freshness_assessments enable row level security;
alter table public.audit_events enable row level security;

-- Client policies are deliberately deferred to FOUND-002. Until then, only the
-- backend service role may access these tables after it validates the caller.