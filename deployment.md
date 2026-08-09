# Recruiting Screening and Scheduling Agent — Demo Deployment

This guide covers the fixture-first client demo and the planned Supabase
deployment boundary. It does not claim production readiness, live ATS/calendar
messaging capability, or legal/compliance certification.

## Target infrastructure

Supabase is the planned hosted system of record: Postgres for jobs, immutable
requirement versions, applications, evidence, evaluations, interviews,
messages, work items, provider events, and audit events. Supabase Auth should own recruiter/candidate identity and
workspace access when authenticated flows are implemented. Supabase Storage is
reserved for approved resume references; do not upload raw candidate files from
the current demo.

The current demo defaults to local SQLite and does not require Supabase
credentials. The server-side Supabase REST boundary is present, but application
and authorization behavior must be verified against a real project before
switching the demo backend.

## Local fixture setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q --basetemp .pytest-temp
python -m apps.api --db .local/demo.sqlite3 --port 8000
```

Open `http://127.0.0.1:8000/` for the candidate/recruiter demo shell. The
fixture path uses SQLite, seeded `retail-job-v1`, and deterministic provider
boundaries.

## Supabase setup (after code verification)

1. Create a Supabase project owned by the client and record the project ref,
   region, owner, retention policy, and backup plan.
2. Apply `supabase/migrations/001_recruiting_demo.sql` using the Supabase SQL
   editor or an approved Supabase CLI pipeline.
3. Verify RLS, service-role access, migration rollback/recovery, and seeded
   requirement data in a non-production project.
4. Configure the server-only backend variables below through the deployment
   platform secret store. Never put the service-role key in `web/`, browser
   JavaScript, `.env.example`, Git history, or client documentation.
5. Run the full test suite and a clean demo rehearsal before enabling the
   Supabase backend.

## Environment and secrets

The repository includes `.env.example` with safe placeholders. The current
fixture mode is secret-free:

| Variable | Purpose | Current status |
|---|---|---|
| `RECRUITING_STORE_BACKEND=sqlite` | Local deterministic store | Default and tested |
| `RECRUITING_SQLITE_PATH` | Local SQLite path | Default `.local/demo.sqlite3` |
| `RECRUITING_STORE_BACKEND=supabase` | Select Supabase REST store | Future integration switch |
| `SUPABASE_URL` | Supabase project URL | Client supplies later |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-only PostgREST/migration access | Secret; never commit |
| `SUPABASE_ANON_KEY` | Future browser/Auth client key | Not used by current UI |
| `RECRUITING_DEMO_CALENDAR_MODE` | Fixture or simulated calendar outage | Fixture default; no live calendar |
| `RECRUITING_DEMO_MESSAGING_MODE` | Fixture or simulated messaging outage | Fixture default; no live sender |

Do not add secrets until the code-level work, migration review, RLS policy, and
workspace authorization tests are complete.

## Demo preflight

1. Confirm `python -m pytest -q --basetemp .pytest-temp` passes.
2. Start the local server and check `/health` reports fixture mode.
3. Open the candidate preview and recruiter requirement/version surfaces.
4. Create or publish a draft through the local HTTP API and verify published
   versions remain immutable.
5. Submit a deterministic candidate application, run screening, inspect the
   evidence matrix, trigger handoff, and record a reasoned recruiter
   disposition.
6. Select `slot-001`, replay the booking request to prove idempotency, move to
   `slot-002`, and replay the calendar callback to prove duplicate protection.
7. Set `RECRUITING_DEMO_CALENDAR_MODE=outage` for the exception path and verify
   a retryable `book_interview` work item without losing application state.
8. Reset `.local/demo.sqlite3` between rehearsals; never use real candidate PII
   in the fixture database.

## Current limitations before client go-live

- Candidate/recruiter UI is a static demo shell; the application evidence and
  pipeline APIs are the authoritative current slice.
- Supabase application persistence, Auth/RLS workspace ownership, resume
  storage, migration CI, backups, monitoring, and incident recovery need live
  project verification.
- ATS, calendar, SMS, and email are fixture-only; no provider credentials or
  scopes are claimed.
- Scheduling and confirmation are deterministic local fixtures. Retryable
  provider work is persisted, but background workers, reminders, live calendar
  reservation, and delivery reconciliation are not implemented yet.
- Screening is deterministic rule evaluation, not a validated model decision;
  final disposition remains recruiter-controlled.
- TLS, authenticated operator access, secret rotation, rate limits, audit
  retention, deletion workflows, and production observability are required
  before external client traffic.

## Handoff checklist

- [ ] Client owns Supabase project, billing, region, backups, Auth settings,
  RLS review, and retention/deletion decisions.
- [ ] Validate migration, seed/reset, service-role scope, and authenticated
  workspace isolation in staging.
- [ ] Add resume upload/download controls with signed URLs and retention rules.
- [ ] Validate one ATS, one calendar, and one consent-aware messaging provider
  behind adapter contracts; label every other capability fixture/blocked.
- [ ] Run accessibility, responsive, screening, handoff, and human-disposition
  acceptance traces from a clean environment.
