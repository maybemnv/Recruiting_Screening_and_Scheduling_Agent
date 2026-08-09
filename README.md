# Recruiting Screening and Scheduling Agent

This checkout contains the first fixture-first Phase 0/1 vertical slice from
`PRD.md`: a local SQLite requirement store, immutable job requirement versions,
the seeded `retail-job-v1` fixture, and a dependency-free HTTP API for the
recruiter job list and candidate-facing question preview.

## Run locally

```powershell
python -m apps.api --db .local/demo.sqlite3 --port 8000
```

Then open:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/api/recruiter/jobs`
- `http://127.0.0.1:8000/api/apply/retail-operations`
- `http://127.0.0.1:8000/api/recruiter/jobs/retail-job/requirements`

The current provider mode is `fixture`: ATS, calendar, SMS, and email are not
called. The SQLite store is a local replacement boundary for the PRD's future
PostgreSQL/FastAPI implementation. No UI has been added yet, so the shared
root design system will be applied when candidate/recruiter pages begin.

## Test

```powershell
python -m pytest -q --basetemp .pytest-temp
```
