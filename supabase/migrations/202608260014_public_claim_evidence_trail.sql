-- Public evidence trail for a single published claim.
--
-- The product's core promise is that every published line traces to an evidence
-- record. This projection is what lets a reader check that trace without an
-- account.
--
-- What it deliberately never returns:
--   * canonical_payload — the observed material itself is private.
--   * source_ref — a reference can name a private repository, so publishing it
--     would leak repository names the owner never chose to disclose. The
--     content hash gives a verifiable fingerprint without that disclosure.
--   * anything belonging to a non-published revision or a non-public profile.

create or replace function public.get_published_claim_evidence(
  p_handle text,
  p_claim_revision_id uuid
)
returns table (
  profile_id uuid,
  handle text,
  display_name text,
  claim_revision_id uuid,
  category text,
  statement text,
  verification_status public.verification_status,
  verifier_score numeric,
  verified_at timestamptz,
  freshness_status public.evidence_validity,
  published_at timestamptz,
  evidence_version_id uuid,
  relation public.evidence_relation,
  source_type text,
  content_hash text,
  version_number integer,
  connector_version text,
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
    profile.id,
    profile.handle,
    profile.display_name,
    claim_revision.id,
    claim.category,
    claim_revision.statement,
    verification.status,
    verification.verifier_score,
    verification.decided_at,
    freshness.status,
    publication.published_at,
    version.id,
    link.relation,
    artifact.source_type,
    version.content_hash,
    version.version_number,
    version.connector_version,
    version.assurance_class,
    version.validity,
    version.observed_at
  from public.profiles as profile
  join public.claims as claim
    on claim.profile_id = profile.id
  join public.claim_revisions as claim_revision
    on claim_revision.claim_id = claim.id
    and claim_revision.profile_id = profile.id
  join public.publications as publication
    on publication.claim_revision_id = claim_revision.id
    and publication.profile_id = profile.id
    and publication.status = 'published'
  join public.verification_decisions as verification
    on verification.id = publication.verification_decision_id
    and verification.profile_id = profile.id
  left join lateral (
    select assessment.status
    from public.freshness_assessments as assessment
    where assessment.claim_revision_id = claim_revision.id
      and assessment.profile_id = profile.id
    order by assessment.assessed_at desc
    limit 1
  ) as freshness on true
  left join public.claim_evidence_links as link
    on link.claim_revision_id = claim_revision.id
  left join public.evidence_versions as version
    on version.id = link.evidence_version_id
    and version.profile_id = profile.id
  left join public.source_artifacts as artifact
    on artifact.id = version.source_artifact_id
    and artifact.profile_id = profile.id
  where profile.handle = p_handle
    and profile.is_public = true
    and claim_revision.id = p_claim_revision_id
  order by link.relation, version.observed_at desc nulls last, version.id;
$$;

revoke all on function public.get_published_claim_evidence(text, uuid) from public, anon, authenticated;
grant execute on function public.get_published_claim_evidence(text, uuid) to service_role;
