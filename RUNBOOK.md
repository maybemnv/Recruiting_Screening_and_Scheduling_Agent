# Local demo runbook

## Health and startup

```powershell
python -m apps.api --db .local/demo.sqlite3 --reset --port 8104
Invoke-RestMethod http://127.0.0.1:8104/health
```

Expected fixture response includes `status: ok`, `mode: sqlite`, and
`providerDependencies: none`, `fixtureReady: true`, and
`seededJobId: retail-job`. With Supabase selected, `mode` reports
`supabase`; this only proves configuration selection, not a live project
read/write rehearsal.

## Reset and recovery

- Stop the local process with `Ctrl+C`.
- Repeat the startup command with `--reset`. Reset is repeat-safe and accepts
  only the explicitly selected `.local/*.sqlite3` fixture; it does not touch
  neighboring databases. Omit `--reset` when preserving a rehearsal.
- Inspect the recruiter application detail for evidence, evaluations,
  work-items, interviews, messages, and audit events.
- Provider outage leaves application state intact and writes a retryable work
  item. Do not blindly replay non-idempotent external writes; use the recorded
  booking/message key and verify provider state first.

## Useful local endpoints

- `GET /api/apply/retail-operations`
- `POST /api/apply/retail-operations/applications`
- `POST /api/applications/{id}/screen`
- `POST /api/applications/{id}/handoff`
- `GET /api/applications/{id}/slots`
- `POST /api/applications/{id}/interviews`
- `POST /api/applications/{id}/reschedule`
- `GET /api/recruiter/applications/{id}`
- `GET /api/recruiter/jobs/retail-job/pipeline?status=review`
- `GET /api/recruiter/jobs/retail-job/analytics`

## Supabase operational boundary

1. Apply `supabase/migrations/001_recruiting_demo.sql` in a client-owned
   non-production project.
2. Confirm RLS is enabled on every table and that only the server-side service
   role can use the current API path. Auth/workspace policies are not yet
   implemented in this prototype.
3. Set secrets through the hosting platform, not a committed `.env` file:
   `RECRUITING_STORE_BACKEND=supabase`, `SUPABASE_URL`, and
   `SUPABASE_SERVICE_ROLE_KEY`.
4. Run the full tests and a clean application/scheduling rehearsal before any
   live provider is enabled.

Never print, return, or place `SUPABASE_SERVICE_ROLE_KEY` in browser assets,
logs, issue comments, screenshots, or client handoff material.

## Browser verification and shutdown

```powershell
Set-Location web
npm ci
npx playwright install chromium
npm run e2e
Set-Location ..
```

There is no static-UI compile step. The browser gate exercises desktop,
keyboard-visible actions/tab navigation, and the 320px candidate flow. After
the walkthrough, use `Ctrl+C` in the server terminal and confirm port 8104 is
no longer listening before deleting any disposable `.local` fixture manually.
