-- Recruiting demo persistence for Supabase/PostgreSQL.
-- Apply with the Supabase SQL editor or the Supabase CLI before selecting
-- RECRUITING_STORE_BACKEND=supabase.  The service role remains server-side.

create table if not exists public.jobs (
    id text primary key,
    slug text not null unique,
    title text not null,
    created_at timestamptz not null default now()
);

create table if not exists public.requirement_versions (
    id text primary key,
    job_id text not null references public.jobs(id),
    version integer not null,
    status text not null check (status in ('draft', 'published', 'retired')),
    published_by text,
    published_at timestamptz,
    unique (job_id, version)
);

create table if not exists public.criteria (
    version_id text primary key references public.requirement_versions(id),
    payload jsonb not null
);

create table if not exists public.applications (
    id text primary key,
    job_id text not null references public.jobs(id),
    requirement_version_id text not null references public.requirement_versions(id),
    external_application_id text,
    contact jsonb not null,
    status text not null default 'received' check (
        status in ('received', 'in_progress', 'awaiting_candidate', 'review',
                   'ready_to_schedule', 'scheduled', 'interviewed',
                   'human_handoff', 'withdrawn', 'dispositioned')
    ),
    consent jsonb not null default '{"sms":"unknown","email":"unknown"}'::jsonb,
    resume_status text not null default 'not_provided' check (
        resume_status in ('not_provided', 'complete', 'uncertain', 'unavailable', 'corrected')
    ),
    resume_file_id text,
    disposition text,
    disposition_reason text,
    dispositioned_by text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.evidence (
    id text primary key,
    application_id text not null references public.applications(id),
    criterion_id text,
    source text not null check (source in ('candidate_answer', 'resume', 'recruiter_override', 'integration')),
    value jsonb,
    source_reference jsonb not null,
    confidence numeric,
    extraction_status text not null check (extraction_status in ('complete', 'uncertain', 'unavailable', 'corrected')),
    created_at timestamptz not null default now()
);

create table if not exists public.evaluations (
    id text primary key,
    application_id text not null references public.applications(id),
    requirement_version_id text not null references public.requirement_versions(id),
    criterion_id text not null,
    result text not null check (result in ('pass', 'fail', 'review', 'not_evaluated')),
    evidence_ids jsonb not null default '[]'::jsonb,
    rule_expression text not null,
    explanation text not null,
    evaluator text not null check (evaluator in ('rule_engine', 'human')),
    evaluated_at timestamptz not null default now(),
    unique (application_id, requirement_version_id, criterion_id)
);

create table if not exists public.work_items (
    id text primary key,
    application_id text references public.applications(id),
    kind text not null,
    idempotency_key text not null unique,
    status text not null default 'queued' check (status in ('queued', 'running', 'succeeded', 'retryable', 'failed', 'cancelled')),
    attempts integer not null default 0,
    last_error_code text,
    next_attempt_at timestamptz,
    reason text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.audit_events (
    id text primary key,
    occurred_at timestamptz not null default now(),
    actor_type text not null check (actor_type in ('candidate', 'recruiter', 'admin', 'agent', 'worker', 'integration')),
    actor_id text,
    action text not null,
    entity_type text not null,
    entity_id text not null,
    before jsonb,
    after jsonb,
    reason text,
    correlation_id text not null,
    source_version text not null
);

create index if not exists idx_applications_job_status on public.applications(job_id, status);
create index if not exists idx_evidence_application on public.evidence(application_id, created_at);
create index if not exists idx_evaluations_application on public.evaluations(application_id, criterion_id);
create index if not exists idx_work_items_status on public.work_items(status, kind);
create index if not exists idx_audit_entity on public.audit_events(entity_type, entity_id, occurred_at);

-- No anon/authenticated policies are intentionally created here.  The demo
-- API uses the server-side service role, while browser access remains through
-- the API boundary.  RLS is fail-closed if a client key is ever misused.
alter table public.jobs enable row level security;
alter table public.requirement_versions enable row level security;
alter table public.criteria enable row level security;
alter table public.applications enable row level security;
alter table public.evidence enable row level security;
alter table public.evaluations enable row level security;
alter table public.work_items enable row level security;
alter table public.audit_events enable row level security;
