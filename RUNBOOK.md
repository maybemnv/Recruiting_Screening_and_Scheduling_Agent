# Local demo runbook

## Health and startup

```powershell
python -m apps.api --db .local/demo.sqlite3 --port 8000
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected fixture response includes `status: ok`, `mode: sqlite`, and
`providerDependencies: none`. With Supabase selected, `mode` reports
`supabase`; this only proves configuration selection, not a live project
read/write rehearsal.

## Reset and recovery

- Stop the local process with `Ctrl+C`.
- Start the next rehearsal with a new `.local/*.sqlite3` path. The generated
  database is disposable fixture state.
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
