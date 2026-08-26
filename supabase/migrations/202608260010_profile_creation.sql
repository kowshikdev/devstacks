-- Fills a golden-path gap found during live testing: nothing previously
-- created a profiles row for a newly signed-up auth.users subject, so every
-- authenticated endpoint 404'd forever. One profile per authenticated
-- subject, created on first use, never reassignable to a different subject.

create or replace function public.create_own_profile(
  p_profile_id uuid,
  p_handle text,
  p_display_name text default null
)
returns public.profiles
language plpgsql
security definer
set search_path = ''
as $$
declare
  profile public.profiles;
begin
  if not exists (select 1 from auth.users where id = p_profile_id) then
    raise exception 'profile id does not match an authenticated subject';
  end if;
  if exists (select 1 from public.profiles where id = p_profile_id) then
    raise exception 'profile already exists for this subject';
  end if;

  insert into public.profiles (id, handle, display_name)
  values (p_profile_id, p_handle, p_display_name)
  returning * into profile;

  return profile;
end;
$$;

revoke all on function public.create_own_profile(uuid, text, text) from public, anon, authenticated;
grant execute on function public.create_own_profile(uuid, text, text) to service_role;
