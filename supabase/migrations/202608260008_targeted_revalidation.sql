-- GH-004: affected-evidence traversal and targeted revalidation.
-- Finds claim revisions linked to superseded evidence versions of one source
-- artifact, and appends freshness assessments without rewriting verification,
-- review, or publication history.

create or replace function public.find_affected_claim_revisions(
  p_profile_id uuid,
  p_source_artifact_id uuid,
  p_changed_evidence_version_id uuid
)
returns table (
  claim_revision_id uuid,
  evidence_version_id uuid
)
language sql
stable
security definer
set search_path = ''
as $$
  select distinct
    link.claim_revision_id,
    link.evidence_version_id
  from public.claim_evidence_links as link
  join public.evidence_versions as version
    on version.id = link.evidence_version_id
  join public.claim_revisions as revision
    on revision.id = link.claim_revision_id
  where version.source_artifact_id = p_source_artifact_id
    and version.profile_id = p_profile_id
    and revision.profile_id = p_profile_id
    and link.evidence_version_id <> p_changed_evidence_version_id;
$$;

create or replace function public.record_freshness_assessment(
  p_profile_id uuid,
  p_claim_revision_id uuid,
  p_status public.evidence_validity,
  p_reason_code text,
  p_recheck_after timestamptz default null
)
returns public.freshness_assessments
language plpgsql
security definer
set search_path = ''
as $$
declare
  assessment public.freshness_assessments;
begin
  if char_length(trim(p_reason_code)) = 0 then
    raise exception 'freshness assessment reason code is required';
  end if;
  if not exists (
    select 1
    from public.claim_revisions
    where id = p_claim_revision_id
      and profile_id = p_profile_id
  ) then
    raise exception 'claim revision does not belong to the profile';
  end if;

  insert into public.freshness_assessments (
    claim_revision_id,
    profile_id,
    status,
    reason_code,
    recheck_after
  )
  values (
    p_claim_revision_id,
    p_profile_id,
    p_status,
    p_reason_code,
    p_recheck_after
  )
  returning * into assessment;

  return assessment;
end;
$$;

revoke all on function public.find_affected_claim_revisions(uuid, uuid, uuid) from public, anon, authenticated;
revoke all on function public.record_freshness_assessment(uuid, uuid, public.evidence_validity, text, timestamptz) from public, anon, authenticated;
grant execute on function public.find_affected_claim_revisions(uuid, uuid, uuid) to service_role;
grant execute on function public.record_freshness_assessment(uuid, uuid, public.evidence_validity, text, timestamptz) to service_role;
