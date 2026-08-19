# Client-demo acceptance matrix

This matrix separates verified local fixture behavior from work that still
needs client-owned Supabase/provider or manual accessibility verification.

| PRD scenario | Evidence in this checkout | Status |
|---|---|---|
| AC-01: publish five retail criteria and screen a passing candidate | `fixtures/retail_job_v1.json`, `tests/test_requirements.py`, `tests/test_phase2_application.py` | Verified locally |
| AC-02: unreadable resume does not fabricate experience | `ApplicationService._evaluate`, `tests/test_phase2_application.py` | Verified locally |
| AC-03: candidate human request pauses screening and queues work | `/api/applications/{id}/handoff`, `tests/test_phase2_application.py` | Verified locally |
| AC-04: duplicate calendar callback creates no duplicate interview | `/api/integrations/calendar/callback`, `tests/test_phase3_scheduling.py` | Verified locally |
| AC-05: reschedule reserves replacement before cancelling old record | `/api/applications/{id}/reschedule`, `tests/test_phase3_scheduling.py` | Verified locally in fixture mode |
| AC-06: missing recruiter reason is rejected and client actor fields cannot control fixture attribution | `/api/applications/{id}/disposition`, `tests/test_phase2_application.py` | Verified locally |
| AC-07: provider outage preserves state and creates retryable work | `RECRUITING_DEMO_CALENDAR_MODE=outage`, `tests/test_phase3_scheduling.py` | Verified locally |
| AC-08: consent/provider result is recorded on confirmation | `apps/api/scheduling.py`, `tests/test_phase3_scheduling.py` | Verified locally for fixture SMS |
| AC-09: pipeline and funnel expose status/version denominator | `/pipeline`, `/analytics`, `tests/test_phase4_analytics.py` | Verified locally |
| AC-10: 500 retail replay reconciles core artifacts | `python -m apps.api.replay`, `tests/test_phase4_analytics.py` | Verified locally |

## Accessibility and operational gates

| PRD gate | Current evidence | Status |
|---|---|---|
| Shared palette, spacing, visible focus, reduced motion, mobile shell | `web/tokens.css`, `web/styles.css`, `web/tests/primary-flow.spec.js` | Verified by Chromium fixture suite |
| Keyboard tab switching and critical action activation with visible focus | `web/tests/primary-flow.spec.js` | Verified by Chromium fixture suite; no assistive-technology claim |
| 320px no-horizontal-scroll candidate flow | `web/tests/primary-flow.spec.js` | Verified by Chromium fixture suite |
| Supabase RLS/Auth workspace isolation | `supabase/migrations/001_recruiting_demo.sql` enables fail-closed RLS; no live project | Not verified |
| Live ATS/calendar/SMS/email behavior | Providers are deliberately fixture-only | Deferred |
| Production secrets, backups, retention, monitoring, TLS, rate limits | Deployment prerequisites are documented, not provisioned here | Not verified |

## Release interpretation

The local fixture prototype is suitable for a controlled client walkthrough of
explicit screening, evidence, human handoff, scheduling, and reconciliation.
It is not a production hiring system until the unverified gates are completed.
