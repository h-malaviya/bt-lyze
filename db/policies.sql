create or replace function public.current_user_role()
returns text
language sql
stable
set search_path = ''
as $$
  select coalesce(
    auth.jwt() -> 'app_metadata' ->> 'role',
    auth.jwt() ->> 'role'
  );
$$;

create or replace function public.current_panel_id()
returns uuid
language sql
stable
set search_path = ''
as $$
  select coalesce(
    auth.jwt() -> 'app_metadata' ->> 'panel_id',
    auth.jwt() ->> 'panel_id'
  )::uuid;
$$;

alter table public.panels enable row level security;
alter table public.profiles enable row level security;
alter table public.candidates enable row level security;
alter table public.recordings enable row level security;
alter table public.transcripts enable row level security;
alter table public.evaluations enable row level security;
alter table public.job_events enable row level security;
alter table public.job_outbox enable row level security;

drop policy if exists panels_select_authorized on public.panels;
create policy panels_select_authorized
on public.panels for select to authenticated
using (public.current_user_role() = 'admin' or id = public.current_panel_id());

drop policy if exists panels_admin_manage on public.panels;
create policy panels_admin_manage
on public.panels for all to authenticated
using (public.current_user_role() = 'admin')
with check (public.current_user_role() = 'admin');

drop policy if exists profiles_select_authorized on public.profiles;
create policy profiles_select_authorized
on public.profiles for select to authenticated
using (public.current_user_role() = 'admin' or id = auth.uid());

drop policy if exists profiles_admin_manage on public.profiles;
create policy profiles_admin_manage
on public.profiles for all to authenticated
using (public.current_user_role() = 'admin')
with check (public.current_user_role() = 'admin');

drop policy if exists candidates_select_authorized on public.candidates;
create policy candidates_select_authorized
on public.candidates for select to authenticated
using (
  public.current_user_role() = 'admin'
  or panel_id = public.current_panel_id()
);

drop policy if exists candidates_panel_insert on public.candidates;
create policy candidates_panel_insert
on public.candidates for insert to authenticated
with check (
  public.current_user_role() = 'panel'
  and panel_id = public.current_panel_id()
  and created_by = auth.uid()
);

drop policy if exists candidates_panel_update on public.candidates;
create policy candidates_panel_update
on public.candidates for update to authenticated
using (
  public.current_user_role() = 'panel'
  and panel_id = public.current_panel_id()
)
with check (
  public.current_user_role() = 'panel'
  and panel_id = public.current_panel_id()
);

drop policy if exists candidates_admin_manage on public.candidates;
create policy candidates_admin_manage
on public.candidates for all to authenticated
using (public.current_user_role() = 'admin')
with check (public.current_user_role() = 'admin');

drop policy if exists recordings_select_authorized on public.recordings;
create policy recordings_select_authorized
on public.recordings for select to authenticated
using (
  public.current_user_role() = 'admin'
  or exists (
    select 1 from public.candidates
    where candidates.id = recordings.candidate_id
      and candidates.panel_id = public.current_panel_id()
  )
);

drop policy if exists transcripts_select_authorized on public.transcripts;
create policy transcripts_select_authorized
on public.transcripts for select to authenticated
using (
  public.current_user_role() = 'admin'
  or exists (
    select 1
    from public.recordings
    join public.candidates on candidates.id = recordings.candidate_id
    where recordings.id = transcripts.recording_id
      and candidates.panel_id = public.current_panel_id()
  )
);

drop policy if exists evaluations_select_authorized on public.evaluations;
create policy evaluations_select_authorized
on public.evaluations for select to authenticated
using (
  public.current_user_role() = 'admin'
  or exists (
    select 1
    from public.recordings
    join public.candidates on candidates.id = recordings.candidate_id
    where recordings.id = evaluations.recording_id
      and candidates.panel_id = public.current_panel_id()
  )
);

drop policy if exists job_events_admin_select on public.job_events;
create policy job_events_admin_select
on public.job_events for select to authenticated
using (public.current_user_role() = 'admin');

drop policy if exists recordings_bucket_select on storage.objects;
create policy recordings_bucket_select
on storage.objects for select to authenticated
using (
  bucket_id = 'recordings'
  and (
    public.current_user_role() = 'admin'
    or (storage.foldername(name))[1] = public.current_panel_id()::text
  )
);

drop policy if exists recordings_bucket_insert on storage.objects;
create policy recordings_bucket_insert
on storage.objects for insert to authenticated
with check (
  bucket_id = 'recordings'
  and public.current_user_role() = 'panel'
  and (storage.foldername(name))[1] = public.current_panel_id()::text
);

drop policy if exists recordings_bucket_delete on storage.objects;
create policy recordings_bucket_delete
on storage.objects for delete to authenticated
using (
  bucket_id = 'recordings'
  and public.current_user_role() = 'panel'
  and (storage.foldername(name))[1] = public.current_panel_id()::text
);

drop policy if exists transcripts_bucket_admin_select on storage.objects;
create policy transcripts_bucket_admin_select
on storage.objects for select to authenticated
using (
  bucket_id = 'transcripts'
  and public.current_user_role() = 'admin'
);
