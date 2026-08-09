# Recruiting Screening and Scheduling Agent — Client Demo Prototype Tasks

**Goal:** Build a recruiter-controlled, auditable prototype that publishes explicit screening criteria, collects a mobile application, explains every criterion result with evidence, schedules or reschedules interviews, and keeps final disposition with a human recruiter.

**Architecture:** Use the PRD boundaries: Next.js candidate and recruiter surfaces, FastAPI typed API, PostgreSQL immutable requirement/evidence/audit state, durable workflow workers, SMS/email workers, and adapter contracts for ATS, calendar, and messaging providers. Deterministic test doubles are the primary client-demo path.

**Tech stack:** Next.js, FastAPI, PostgreSQL, workflow engine, SMS and email workers, and adapters for Greenhouse, Lever, Ashby, Workday, Twilio, Google Calendar, and Microsoft 365, as bounded by `PRD.md`.

## Global constraints

- [ ] Preserve human accountability: the agent can recommend `pass`, `fail`, `review`, or `not_evaluated`, but cannot finalize hire/reject or bypass recruiter review.
- [ ] Every decision-bearing result links to requirement version, criterion ID, rule, evidence, evaluator/model version, actor, timestamp, and correlation ID.
- [ ] Unreadable resumes, ambiguous answers, accessibility barriers, human requests, worker failures, and provider failures route to visible review or handoff work; never fabricate evidence.
- [ ] Use one published retail job and deterministic ATS, calendar, SMS, and email fixtures for the demo; mark provider capabilities as live, fixture, blocked, or uncertain.
- [ ] Use `D:\ARC Automation Service\design.md` as the shared visual authority for genre, shell, palette, typography, spacing, shape, motion, and explicit states. Adapt it to candidate/recruiter surfaces; do not copy call or revenue content.
- [ ] Keep the PRD out-of-scope boundary: no autonomous hire/reject, opaque ranking, executive recruiting, native apps, sourcing, outbound campaigns, offers, compensation, onboarding, payroll, background checks, video/voice interviewing, or legal/compliance certification.

## Current status - 2026-08-09

### Delivered in the first vertical slice

- [x] Added a fixture-first local SQLite requirement store under `apps/api/`.
- [x] Seeded `retail-job-v1` from `fixtures/retail_job_v1.json` with the five PRD criteria: work authorization, availability, location, experience, and interview slot.
- [x] Implemented criterion validation, draft creation, publication, immutable published versions, and candidate-facing preview generation.
- [x] Added a dependency-free local HTTP API with recruiter job listing, recruiter requirements, candidate preview, and health endpoints.
- [x] Added requirement validation, draft criteria replacement, publish, version history, and precise JSON error responses.
- [x] Added a design-tokenized candidate/recruiter static demo shell with mobile layout, visible focus, text-plus-state badges, and explicit loading/error states.
- [x] Added a server-side Supabase REST boundary, credential-free backend selection, `.env.example`, and an RLS-enabled migration for the future application/evidence/audit tables.
- [x] Added fixture-first candidate application intake, consent/resume state, version-linked deterministic screening, evidence/evaluation records, review/handoff work items, recruiter detail/pipeline reads, and human-reason disposition controls.
- [x] Added fixture calendar slot availability, time-zone-aware booking, idempotent confirmation replay, replacement-first rescheduling, duplicate callback reconciliation, and retryable provider-degraded work items.
- [x] Added pipeline filters, denominator-aware funnel analytics, and a deterministic 500-application reconciliation command.
- [x] Added TDD coverage for immutable versions, preview consistency, HTTP version history/mutations, backend configuration, application screening, evidence, handoff, disposition, scheduling, callbacks, analytics, replay, and the local API/UI surface: 21 tests passing.
- [x] Added local run instructions and ignored generated SQLite/test scratch paths.

### Not yet complete

- [x] Added a small candidate/recruiter fixture demo shell with the shared root design schema, preview, and version-state interactions.
- [ ] Full production candidate/recruiter application surfaces remain outstanding, but the fixture demo shell now submits applications, shows screening states, books/reschedules slots, and opens recruiter evidence/pipeline detail.
- [ ] The Phase 0 design mapping, acceptance matrix, seeded actor accounts, and full typed domain contracts remain outstanding.
- [x] The local Phase 1/2 API captures candidate applications and exposes screening, evidence, pipeline, handoff, and disposition behavior against SQLite.
- [ ] Durable Supabase application writes, authenticated workspace access, workers, reminder delivery, live provider adapters, and full audit/analytics UI remain outstanding; the local scheduling path is fixture-backed and verified.

### Next work queue

1. Add candidate correction/approved FAQ behavior, reminder work items, bounded retries, and provider capability inspection.
2. Verify Supabase writes, RLS/Auth workspace ownership, seed/reset, and migration recovery in a client staging project.
3. Add live ATS/calendar/messaging adapters only after client provider decisions and contract tests.
4. Complete manual accessibility review, monitoring attributes, and final client-owned go-live decisions.

The pre-existing task checklist remains the source of the full Phase 0-4 scope; this status records only verified work in the current checkout.

## Target file structure

- Create `apps/web/` for candidate and recruiter routes, components, tokens, and typed client.
- Create `apps/api/` for job, requirements, applications, evaluations, scheduling, handoff, audit, analytics, and adapter APIs.
- Create `workers/` for resume extraction, screening, reminders, calendar reconciliation, messaging, ATS sync, and retry work.
- Create `db/migrations/` and `db/seed_retail_demo.sql` for jobs, immutable criteria, applications, evidence, evaluations, interviews, work items, funnel events, and audit records.
- Create `adapters/` for ATS, calendar, SMS, and email interfaces plus deterministic test doubles.
- Create `tests/contracts/`, `tests/workflows/`, `tests/accessibility/`, `tests/traces/`, and `tests/analytics/` for API, safety, UI, trace, and metric coverage.
- Create `README.md`, `.env.example`, `DEMO_SCRIPT.md`, `RUNBOOK.md`, and `ACCEPTANCE_MATRIX.md` for client operation.

## Phase 0 — Demo contract, design mapping, and foundation

- [ ] Convert PRD acceptance scenarios AC-01–AC-10, accessibility requirements A11Y-01–A11Y-09, metrics M-01–M-11, and Q-01 into `ACCEPTANCE_MATRIX.md`.
- [ ] Scaffold the candidate, recruiter, API, database, worker, adapter, and test boundaries without committing secrets or unverified provider versions.
- [ ] Define typed contracts for job versions, criteria, candidate evidence, evaluation results, work items, interviews, messages, sync state, monitoring attributes, and audit events.
- [ ] Adapt the root `design.md` schema into a candidate mobile flow and recruiter desktop workbench: stat strip, review surface, supporting evidence panels, floating-pill navigation, inline operational footer, explicit loading/error states, 4-point spacing, 1px rules, restrained corners, no gradients/glass, and visible focus.
- [ ] Resolve the token-path mismatch by choosing one CSS token source and mapping semantic pass/review/failure/booking aliases without mixing incompatible visual systems.
- [ ] Define seeded accounts for candidate, recruiter, reviewer, administrator, and provider test doubles.

**Exit gate:** A clean checkout starts in demo mode and the recruiter/candidate surfaces show the same published job version and expected state labels.

## Phase 1 - Requirements, versioning, and candidate entry

- [x] Implement local job draft creation, criterion validation, candidate-facing wording preview, publication, and immutable requirement versions.
- [x] Seed `retail-job-v1` with work authorization, availability, location, experience, and interview-slot criteria.
- [x] Reject invalid or unsupported criteria at local draft, replacement, validation, and publish boundaries with safe JSON validation reasons; policy blocklists and audit records remain outstanding.
- [x] Build the fixture `/apply/{jobSlug}` shell with contact capture, ordered questions, consent context, resume status, screening preview, saved/error state, human-help path, slot selection, rescheduling, and mobile layout; production routing/auth remains outstanding.
- [x] Build the fixture recruiter requirements/pipeline/evidence shell with job state, criteria, published version, candidate rows, and application detail; publish controls, filters, and authenticated workspace remain outstanding.
- [x] Add tests proving candidate wording matches the published version and later edits create a new version without mutating old results.

**Demo gate:** A recruiter publishes the retail job, the candidate opens the flow at 320px width, and version 1 is immutable.

## Phase 2 — Screening, evidence, explainability, and handoff

- [x] Capture ordered answers, consent context, resume file references, extraction status, evidence spans, confidence, and source references.
- [x] Implement deterministic rule evaluation with `pass`, `fail`, `review`, and `not_evaluated` results tied to the requirement version and criterion.
- [x] Implement unreadable-resume behavior: extraction is `unavailable`, missing experience remains unknown, and the application enters `review` or `human_handoff`.
- [ ] Implement ambiguous-answer normalization to `review`, candidate correction, approved FAQ responses, unsupported-question handoff, and recruiter review work items.
- [x] Build `/recruiter/jobs/{jobId}/pipeline` with initial status counts, candidate rows, and evidence open action; filters remain outstanding.
- [x] Build `/recruiter/applications/{applicationId}` detail with evidence matrix, rule explanation, source, confidence, audit expansion, messages, scheduling, and next human action in the fixture shell; authenticated UI remains outstanding.
- [x] Append audit events for candidate answers, extraction, evaluation, correction, override, handoff, and disposition where those local actions exist.
- [x] Add tests proving no agent or worker can create a final hire/reject disposition.

**Demo gate:** A candidate submits a resume and answers; the recruiter sees each criterion’s evidence and explanation and can take over any ambiguous case.

## Phase 3 — Scheduling, messaging, and integration boundaries

- [x] Implement durable work-item records, correlation IDs, booking/message idempotency keys, provider-degraded state, and manual recovery tasks for the fixture path; bounded worker retries remain outstanding.
- [x] Implement fixture calendar adapter interfaces for slot listing, reserve, release-by-cancellation, and callback reconciliation.
- [x] Implement fixture slot selection, Chicago time-zone display, confirmation, consent check, provider result, and visible provider failure state; reminders and opt-out delivery remain outstanding.
- [x] Implement replacement-first rescheduling: reserve the new slot, keep the old slot until success, then release it and send one updated confirmation.
- [x] Ensure duplicate calendar callbacks reconcile by provider event identity or booking key and create exactly one active interview.
- [ ] Implement ATS adapter contracts and test doubles for Greenhouse, Lever, Ashby, and Workday; keep live mappings behind explicit capabilities.
- [ ] Add integration health, retry, `sync_pending`, provider failure, and manual handoff UI.
- [ ] Add tests for duplicate callbacks, auth failure, rate limit, malformed payload, provider outage, partial write, booking failure, and idempotent ATS updates.

**Demo gate:** A passing candidate selects a slot, receives confirmation, reschedules safely, and sees a provider failure become visible recruiter work.

## Phase 4 — Recruiter operations, analytics, accessibility, and hardening

- [ ] Build scorecard views that separate automated criterion results, overrides, and final human disposition; do not show an opaque composite rank.
- [x] Build fixture funnel analytics by job version, stage, date range, and denominator; show denominator, missingness, and timestamp definition.
- [ ] Add access-controlled monitoring attributes, data sufficiency, adverse-outcome flags, alert owner, investigation status, review note, and resolution event; keep monitoring data out of criterion evaluation.
- [x] Apply the shared design tokens with text-plus-state status, candidate progress, saved/error states, readable tables, and stacked mobile cards; full browser QA remains outstanding.
- [ ] Verify keyboard-only operation, labels/errors, visible focus, live-region updates, 320px candidate flow, zoom, manual-entry fallback, human assistance, and local/canonical time zones.
- [x] Replay 500 retail applications and reconcile applications, evaluations, evidence, work items, audit events, and funnel counts; live ATS/interview/message reconciliation remains fixture-limited.
- [ ] Add integration health, secret redaction, audit expansion, retry recovery, and `sync_pending` state inspection.

**Demo gate:** The recruiter reviews the pipeline, evidence scorecard, funnel, audit record, scheduling state, and adverse-outcome monitoring limitations for 500 applications.

## Client demo scenario

1. Publish `retail-job-v1` with work authorization, availability, location, experience, and interview-slot criteria.
2. Open the candidate flow, submit a resume, answer all five questions, and select a Chicago-time-zone slot.
3. Show versioned evaluations, evidence, rule explanations, scheduled state, confirmation, and reminder trace.
4. Open the recruiter pipeline and application detail; show that final disposition is still a recruiter action.
5. Run the exception path with unreadable resume, ambiguous availability, human request, manual evidence correction, and replacement-first rescheduling.
6. Replay a duplicate calendar callback and show one active interview.
7. Simulate provider failure and show visible retry/manual work rather than lost state.
8. Show funnel denominators, scorecard, audit trail, monitoring data limitations, and the 500-application reconciliation.

## Validation and handoff

- [ ] Run contract tests for authorization, typed HTTP responses, immutable versions, reason-required override/disposition, and adapter interfaces.
- [ ] Run workflow tests for consent, evidence linkage, no-fabrication, idempotency, duplicate callbacks, retry boundaries, provider failure, ATS `sync_pending`, and replacement-first rescheduling.
- [ ] Run end-to-end tests for AC-01 through AC-10 and both PRD traces.
- [ ] Run accessibility and responsive tests for A11Y-01 through A11Y-09, including keyboard, focus, labels, live regions, 320px width, manual entry, handoff, and time zones.
- [ ] Verify M-03 duplicate interview rate is zero, M-05 message traceability is 100%, M-06 audit completeness is 100%, M-07 human disposition coverage is 100%, M-08 ATS reconciliation is 100% in adapter tests, M-09 release-blocking accessibility defects are zero, M-10 500-application reconciliation is 100%, M-11 alerts are investigated, and Q-01 is observable.
- [x] Add `README.md` with setup, migration target, seed/reset commands, demo mode, test doubles, environment variables, and known limitations.
- [x] Add `DEMO_SCRIPT.md` with fixture happy/exception paths, expected evidence, provider labels, and fallback steps.
- [x] Add `RUNBOOK.md` with local recovery, correlation IDs, retry/manual handoff, calendar reconciliation, messaging consent, audit interpretation, and incident procedure.
- [x] Add `ACCEPTANCE_MATRIX.md` mapping the implemented acceptance scenarios to evidence, explicit deferral, or blocker.
- [x] Add `deployment.md` with verified infrastructure, setup, environment-variable, provider-mode, demo launch, health-check, rollback, and client handoff guidance.
- [ ] Record client-owned decisions for first live ATS/calendar, sender, prohibited criteria, monitoring attributes, retention/deletion, model/extractor versions, and observed throughput; do not invent them.

## Final acceptance gates

- [ ] The retail happy path runs from application intake through scheduled interview and recruiter disposition.
- [ ] The unreadable/ambiguous/human-handoff/reschedule path is visible and recoverable.
- [ ] No agent or worker can finalize hire or reject.
- [ ] Every decision-bearing event includes actor, version, timestamp, evidence, and required reason.
- [ ] Duplicate callbacks do not create duplicate interviews or messages.
- [ ] Candidate and recruiter flows meet keyboard, focus, labeling, responsive, and time-zone requirements.
- [ ] The demo is repeatable from fixtures, and all provider limitations are clearly labeled for client fine-tuning.
