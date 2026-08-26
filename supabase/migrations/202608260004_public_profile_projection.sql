-- Public profile data is exposed only through a server-invoked projection.
-- It never returns private evidence payloads, source credentials, or non-published revisions.

create or replace function public.get_published_profile(p_handle text)
returns table (
  profile_id uuid,
  handle text,
  display_name text,
  claim_revision_id uuid,
  category text,
  statement text,
  assurance_class text,
  freshness_status public.evidence_validity,
  last_verified_at timestamptz
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
    evidence.assurance_class,
    freshness.status,
    verification.decided_at
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
  join lateral (
    select decision.decided_at
    from public.verification_decisions as decision
    where decision.id = publication.verification_decision_id
      and decision.profile_id = profile.id
    limit 1
  ) as verification on true
  left join lateral (
    select assessment.status
    from public.freshness_assessments as assessment
    where assessment.claim_revision_id = claim_revision.id
      and assessment.profile_id = profile.id
    order by assessment.assessed_at desc
    limit 1
  ) as freshness on true
  left join lateral (
    select version.assurance_class
    from public.claim_evidence_links as link
    join public.evidence_versions as version
      on version.id = link.evidence_version_id
      and version.profile_id = profile.id
    where link.claim_revision_id = claim_revision.id
      and link.relation = 'supports'
    order by version.observed_at desc nulls last, version.fetched_at desc
    limit 1
  ) as evidence on true
  where profile.handle = p_handle
    and profile.is_public = true
  order by claim.category, claim_revision.created_at, claim_revision.id;
$$;

revoke all on function public.get_published_profile(text) from public, anon, authenticated;
grant execute on function public.get_published_profile(text) to service_role;