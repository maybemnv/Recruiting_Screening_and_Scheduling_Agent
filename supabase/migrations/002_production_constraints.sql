-- Production hardening layered on 001 without rewriting applied history.
alter table public.applications
  add column if not exists resume_deleted_at timestamptz,
  add column if not exists retention_due_at timestamptz;

create index if not exists idx_applications_resume_retention
  on public.applications (retention_due_at)
  where resume_file_id is not null and resume_deleted_at is null;

create unique index if not exists uq_applications_external_identity
  on public.applications (job_id, external_application_id)
  where external_application_id is not null;

create index if not exists idx_provider_events_type_created
  on public.provider_events (event_type, created_at);

-- The API uses the server-side service role. Direct browser access remains
-- denied by the existing fail-closed RLS posture until workspace claims are
-- provisioned in the target Supabase Auth project.
