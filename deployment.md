# Recruiting Screening and Scheduling Agent — Demo Deployment

This guide covers the fixture-first client demo and the Supabase deployment
boundary. It does not claim production readiness, live ATS/calendar messaging
capability, or legal/compliance certification.

## Target infrastructure

Supabase is the planned hosted system of record: Postgres for jobs, immutable
requirement versions, applications, evidence, evaluations, interviews,
messages, work items, provider events, and audit events. Supabase Auth should own recruiter/candidate identity and
workspace access when authenticated flows are implemented. Supabase Storage is
reserved for approved resume references; do not upload raw candidate files from
the current demo.

The current demo defaults to local SQLite and does not require Supabase
credentials. The server-side Supabase REST boundary and application tables are
implemented, but application writes, RLS, and authorization behavior must be
verified against a real project before switching the demo backend.

## Local fixture setup

```powershell
python -m pytest -q --basetemp .pytest-temp
python -m apps.api --db .local/demo.sqlite3 --reset --port 8104
```

The API uses Python standard-library modules. Install `pytest` only in the
developer/test environment if it is not already available. Browser tooling is
committed under `web/`; the static UI has no compile step.

```powershell
Set-Location web
npm ci
npx playwright install chromium
npm run e2e
Set-Location ..
```

Open `http://127.0.0.1:8104/` for the candidate/recruiter demo shell. The
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
| `RECRUITING_STORE_BACKEND=supabase` | Select Supabase REST store | Implemented; live project unverified |
| `SUPABASE_URL` | Supabase project URL | Client supplies later |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-only PostgREST/migration access | Secret; never commit |
| `SUPABASE_ANON_KEY` | Future browser/Auth client key | Not used by current UI |
| `RECRUITING_DEMO_CALENDAR_MODE=fixture` | Deterministic calendar mode; use `outage` to rehearse provider failure | Fixture-tested |
| `RECRUITING_DEMO_MESSAGING_MODE=fixture` | Deterministic messaging mode; use `outage` to rehearse delivery failure | Fixture-tested; live messaging not called |
| `RECRUITING_DEMO_CALENDAR_MODE` | Fixture or simulated calendar outage | Fixture default; no live calendar |
| `RECRUITING_DEMO_MESSAGING_MODE` | Fixture or simulated messaging outage | Fixture default; no live sender |

Do not add secrets until the code-level work, migration review, RLS policy, and
workspace authorization tests are complete.

## Demo preflight

1. Confirm `python -m pytest -q --basetemp .pytest-temp` passes.
2. Start the local server on 8104 and check `/health` reports `mode: sqlite`,
   `providerDependencies: none`, `fixtureReady: true`, and the seeded job.
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
8. Reset only the explicit `.local/demo.sqlite3` fixture with `--reset`; repeat
   it to prove idempotency and never use real candidate PII.
9. Stop with `Ctrl+C`; this lightweight service intentionally has no Docker
   requirement for the showcase.

## Current limitations before client go-live

- Candidate/recruiter UI is a static fixture demo with an automated desktop,
  keyboard, and 320px browser gate; it is not production authentication.
- Supabase application persistence is coded but needs live project verification;
  Auth/RLS workspace ownership, resume storage, migration CI, backups,
  monitoring, and incident recovery are not provisioned here.
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

## Deploy/rollback decision

No hosting provider, Dockerfile, worker runtime, domain, or client Supabase
project was specified in the PRD or checkout. Do not invent one for go-live.
The client must choose the API host, TLS/domain owner, process supervisor,
backup/restore policy, log retention, and Supabase region. Before switching a
staging environment to Supabase, export/backup the project and rehearse the
migration plus seed. Rollback is a hosting revision rollback plus restoration
of the approved database backup; there is no destructive down-migration in
this repository.

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
- [ ] Client supplies hosting target, domain/TLS owner, Supabase project,
  service-role secret, Auth/workspace policy, backups, retention/deletion,
  first live providers, sender identity, and incident contact.
