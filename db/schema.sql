create extension if not exists pgcrypto;

do $$ begin
  create type public.user_role as enum ('admin', 'panel');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.verdict as enum ('selected', 'not_decided', 'not_selected');
exception when duplicate_object then null;
end $$;

do $$ begin
  if exists (
    select 1
    from pg_enum
    join pg_type on pg_type.oid = pg_enum.enumtypid
    join pg_namespace on pg_namespace.oid = pg_type.typnamespace
    where pg_namespace.nspname = 'public'
      and pg_type.typname = 'verdict'
      and pg_enum.enumlabel = 'confused'
  ) then
    alter type public.verdict rename value 'confused' to 'not_decided';
  end if;
end $$;

do $$ begin
  create type public.job_stage as enum (
    'uploaded',
    'queued',
    'transcribing',
    'transcribed',
    'analyzing',
    'completed',
    'failed'
  );
exception when duplicate_object then null;
end $$;

create table if not exists public.panels (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(name) between 1 and 100),
  interviewer_1 text,
  interviewer_2 text,
  auth_user_id uuid unique references auth.users(id) on delete set null,
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  role public.user_role not null default 'panel',
  panel_id uuid references public.panels(id) on delete set null,
  full_name text,
  created_at timestamptz not null default now(),
  constraint panel_role_requires_panel check (role = 'admin' or panel_id is not null)
);

create table if not exists public.candidates (
  id uuid primary key default gen_random_uuid(),
  external_id text not null,
  full_name text not null check (char_length(full_name) between 1 and 200),
  category text not null check (category in ('ai_ml', 'full_stack_engineer')),
  panel_id uuid not null references public.panels(id),
  verdict public.verdict not null default 'selected',
  notes text check (char_length(notes) <= 5000),
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  search_tsv tsvector generated always as (
    to_tsvector(
      'english',
      coalesce(full_name, '') || ' ' || coalesce(external_id, '') || ' ' || coalesce(notes, '')
    )
  ) stored
);

alter table public.candidates
  add column if not exists category text;

alter table public.candidates
  drop constraint if exists candidates_category_valid;
alter table public.candidates
  add constraint candidates_category_valid
  check (category is not null and category in ('ai_ml', 'full_stack_engineer')) not valid;

alter table public.candidates
  drop constraint if exists candidates_external_id_required;
alter table public.candidates
  add constraint candidates_external_id_required
  check (external_id is not null and btrim(external_id) <> '') not valid;

do $$ begin
  if not exists (select 1 from public.candidates where external_id is null) then
    alter table public.candidates alter column external_id set not null;
  end if;
end $$;

update public.candidates set verdict = 'selected' where verdict is null;
alter table public.candidates alter column verdict set default 'selected';
alter table public.candidates alter column verdict set not null;

create table if not exists public.recordings (
  id uuid primary key default gen_random_uuid(),
  candidate_id uuid not null references public.candidates(id) on delete cascade,
  storage_provider text not null default 'supabase',
  storage_container text not null default 'recordings',
  storage_path text not null,
  original_filename text,
  duration_sec integer check (duration_sec is null or duration_sec >= 0),
  size_bytes bigint check (size_bytes is null or size_bytes >= 0),
  mime_type text,
  stage public.job_stage not null default 'uploaded',
  attempt_count integer not null default 0 check (attempt_count >= 0),
  last_error text,
  deepgram_request_id text unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint recordings_storage_provider_valid
    check (storage_provider in ('supabase', 'azure'))
);

alter table public.recordings
  add column if not exists original_filename text;

alter table public.recordings
  add column if not exists storage_provider text not null default 'supabase',
  add column if not exists storage_container text not null default 'recordings';

alter table public.recordings
  drop constraint if exists recordings_storage_path_key;

do $$ begin
  alter table public.recordings
    add constraint recordings_storage_provider_valid
    check (storage_provider in ('supabase', 'azure'));
exception when duplicate_object then null;
end $$;

create table if not exists public.transcripts (
  id uuid primary key default gen_random_uuid(),
  recording_id uuid not null unique references public.recordings(id) on delete cascade,
  storage_path text,
  text text,
  words jsonb,
  language text,
  provider_meta jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.evaluations (
  id uuid primary key default gen_random_uuid(),
  recording_id uuid not null references public.recordings(id) on delete cascade,
  version integer not null default 1 check (version > 0),
  is_current boolean not null default true,
  overall_score smallint check (overall_score between 1 and 5),
  scores jsonb not null,
  summary text not null,
  strengths text[] not null default '{}',
  concerns text[] not null default '{}',
  recommendation text check (recommendation in ('selected', 'not_selected', 'borderline')),
  prompt_version text not null,
  model text,
  token_usage jsonb,
  created_at timestamptz not null default now(),
  unique (recording_id, version)
);

create table if not exists public.job_events (
  id bigserial primary key,
  recording_id uuid not null references public.recordings(id) on delete cascade,
  stage public.job_stage,
  status text not null check (status in ('started', 'succeeded', 'failed', 'retry')),
  detail text,
  created_at timestamptz not null default now()
);

create table if not exists public.job_outbox (
  id bigserial primary key,
  recording_id uuid not null references public.recordings(id) on delete cascade,
  job_name text not null check (job_name = 'process_recording'),
  status text not null default 'pending' check (status in ('pending', 'dispatched')),
  attempt_count integer not null default 0 check (attempt_count >= 0),
  last_error text,
  available_at timestamptz not null default now(),
  dispatched_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (recording_id, job_name)
);

create index if not exists candidates_panel_id_idx on public.candidates (panel_id);
create index if not exists candidates_verdict_idx on public.candidates (verdict);
create index if not exists candidates_created_at_idx on public.candidates (created_at desc);
create index if not exists candidates_search_idx on public.candidates using gin (search_tsv);
create index if not exists recordings_candidate_id_idx on public.recordings (candidate_id);
create index if not exists recordings_stage_idx on public.recordings (stage);
create unique index if not exists recordings_storage_object_idx
  on public.recordings (storage_provider, storage_container, storage_path);
create index if not exists evaluations_recording_id_idx on public.evaluations (recording_id);
create unique index if not exists evaluations_one_current_idx
  on public.evaluations (recording_id)
  where is_current;
create index if not exists evaluations_overall_score_idx on public.evaluations (overall_score);
create index if not exists job_events_recording_created_idx
  on public.job_events (recording_id, created_at desc);
create index if not exists job_outbox_pending_idx
  on public.job_outbox (available_at, id)
  where status = 'pending';

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists candidates_set_updated_at on public.candidates;
create trigger candidates_set_updated_at
before update on public.candidates
for each row execute function public.set_updated_at();

drop trigger if exists recordings_set_updated_at on public.recordings;
create trigger recordings_set_updated_at
before update on public.recordings
for each row execute function public.set_updated_at();

drop trigger if exists job_outbox_set_updated_at on public.job_outbox;
create trigger job_outbox_set_updated_at
before update on public.job_outbox
for each row execute function public.set_updated_at();

insert into storage.buckets (id, name, public)
values
  ('recordings', 'recordings', false),
  ('transcripts', 'transcripts', false)
on conflict (id) do update set public = false;

create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  requested_role public.user_role;
  requested_panel_id uuid;
begin
  requested_role := coalesce(new.raw_app_meta_data ->> 'role', 'panel')::public.user_role;
  requested_panel_id := (new.raw_app_meta_data ->> 'panel_id')::uuid;

  if requested_role = 'admin' or requested_panel_id is not null then
    insert into public.profiles (id, role, panel_id, full_name)
    values (
      new.id,
      requested_role,
      requested_panel_id,
      new.raw_user_meta_data ->> 'full_name'
    )
    on conflict (id) do update set
      role = excluded.role,
      panel_id = excluded.panel_id,
      full_name = excluded.full_name;
  end if;

  return new;
end;
$$;

drop trigger if exists auth_user_created on auth.users;
create trigger auth_user_created
after insert or update of raw_app_meta_data, raw_user_meta_data on auth.users
for each row execute function public.handle_new_auth_user();

grant usage on schema public to authenticated, service_role;
grant select on public.panels, public.profiles to authenticated;
grant select, insert, update on public.candidates to authenticated;
grant select on public.recordings, public.transcripts, public.evaluations to authenticated;
grant select on public.job_events to authenticated;
grant all on all tables in schema public to service_role;
grant all on all sequences in schema public to service_role;
