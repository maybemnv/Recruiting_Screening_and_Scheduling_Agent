# Recruiting Screening and Scheduling Agent

This checkout contains the fixture-first recruiting prototype from `PRD.md`: a
local SQLite test double, a Supabase/PostgreSQL migration target, immutable job
requirement versions, the seeded `retail-job-v1` fixture, a dependency-free
HTTP API, and a static candidate / recruiter workbench.

## Run locally

```powershell
python -m apps.api --db .local/demo.sqlite3 --port 8000
```

Then open:

- `http://127.0.0.1:8000/` (candidate and recruiter demo shell)
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/api/recruiter/jobs`
- `http://127.0.0.1:8000/api/apply/retail-operations`
- `http://127.0.0.1:8000/api/recruiter/jobs/retail-job/requirements`

Requirement mutation endpoints are available for the local recruiter flow:

- `POST /api/jobs/{jobId}/requirement-versions/validate`
- `POST /api/jobs/{jobId}/requirement-versions`
- `PUT /api/jobs/{jobId}/requirement-versions/{versionId}/criteria`
- `POST /api/jobs/{jobId}/requirement-versions/{versionId}/validate`
- `POST /api/jobs/{jobId}/requirement-versions/{versionId}/publish`
- `GET /api/recruiter/jobs/{jobId}/requirements/history`

The current provider mode is `fixture`: ATS, calendar, SMS, and email are not
called. Set `RECRUITING_STORE_BACKEND=supabase` after applying
`supabase/migrations/001_recruiting_demo.sql` and supplying the server-only
variables in `.env.example`; the browser must never receive the Supabase
service-role key. SQLite remains the credential-free deterministic test mode.
The UI adapts the root design schema using the shared brand palette, type,
spacing, visible focus, reduced motion, and explicit status/error states.

## Test

```powershell
python -m pytest -q --basetemp .pytest-temp
```
