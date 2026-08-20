# Plan 001: Complete and verify the fixture candidate-to-recruiter showcase

> **Executor instructions**: Work test first. For each behavior, add one focused failing test, run it and observe the intended RED failure, implement the smallest GREEN change, then refactor only while green. Run all verification gates. If a STOP condition occurs, report it instead of expanding the task. After approved review, update `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat ca1984a..HEAD -- apps/api/__main__.py apps/api/server.py apps/api/applications.py web tests README.md RUNBOOK.md DEMO_SCRIPT.md deployment.md .env.example plans`
> If the current code no longer matches the excerpts below, stop and report the drift before modifying source.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED
- **Depends on**: none
- **Category**: bug, tests, dx, docs
- **Planned at**: commit `ca1984a`, 2026-08-19

## Why this matters

The fixture backend already creates evidence, screening outcomes, schedule/reschedule records, human dispositions, and funnel analytics. The browser only shows a partial candidate flow and a pipeline/evidence preview; it neither records the final human decision nor displays analytics. This plan makes the complete story demonstrable in a browser at desktop and mobile widths, with a server-owned fixture reviewer identity and repeatable local launch/reset evidence.

## Current state

- `apps/api/__main__.py:10-17` defaults to `.local/demo.sqlite3` and port `8000`; it seeds through `create_demo_server` but has no reset option.
- `apps/api/server.py:165-174` serves `/health`; `server.py:409-420` passes request-supplied `actorType` and `actorId` to disposition.
- `apps/api/applications.py:274-312` requires `actor_type == "recruiter"`, a reason, and a supported disposition, but it trusts the caller’s string. `applications.py:435-467` already returns funnel stages and final human-recorded count.
- `web/index.html:18-21` exposes Candidate/Recruiter tabs; `web/index.html:31,89` refers to tab panels but tab IDs/controls are incomplete. `web/index.html:89-125` has no disposition or analytics UI.
- `web/app.js:96-102` renders only a small detail; `web/app.js:189-197` opens that detail; it never calls disposition or analytics. Use its existing `escapeHtml` helper at lines 8-13 for all new server data.
- Existing tests are Python HTTP/service tests. `tests/test_phase1_surface.py:75-98` fetches assets and checks strings; no browser runner/configuration exists. `ACCEPTANCE_MATRIX.md` records keyboard and 320px verification as unverified.
- The product intent requires a recruiter-controlled final disposition with actor and reason, keyboard-only flows, mobile candidate flow, evidence/audit/scheduling inspection, and funnel analytics. Live providers remain optional.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Branch | `git switch -c feat/demo-showcase-ready` | branch created |
| Focused/full API tests | `python -m pytest -q --basetemp .pytest-temp` | all tests pass |
| Fixture launch | `python -m apps.api --db .local/demo.sqlite3 --port 8104` | server announces `8104` |
| Health | `Invoke-RestMethod http://127.0.0.1:8104/health` | fixture SQLite-ready response |
| Browser install | `cd web; npm ci; npx playwright install chromium` | dependencies and browser installed |
| Browser suite | `cd web; npm run e2e` | desktop, mobile, keyboard tests pass |

The executor must add the minimal committed browser-test tooling required by this plan (including lockfile) rather than relying on a globally installed runner. The static UI has no production build step; document that explicitly and use the browser suite as its frontend verification gate.

## Suggested executor toolkit

- Use `superpowers:test-driven-development` for API and browser behavior changes.
- In an executor/subagent workflow, dispatch one logical task at a time and review each checkpoint before beginning the next; no worker may broaden the scope or dispatch additional workers.

## Scope

**In scope** (only these paths may change):

- `apps/api/__main__.py`, `apps/api/server.py`, `apps/api/applications.py`
- `web/index.html`, `web/app.js`, `web/styles.css`, plus new committed browser tooling/config/spec files under `web/`
- `tests/test_local_api.py`, `tests/test_phase1_surface.py`, `tests/test_phase2_application.py`, `tests/test_phase3_scheduling.py`, `tests/test_phase4_analytics.py`, and new focused Python tests under `tests/`
- `README.md`, `RUNBOOK.md`, `DEMO_SCRIPT.md`, `deployment.md`, `.env.example`, `ACCEPTANCE_MATRIX.md`, `plans/README.md`

**Out of scope**:

- Live Supabase project/RLS validation, provider credentials, actual ATS/calendar/SMS/email calls, production login, hosting, TLS, or resume upload/storage.
- Framework migration, a Next.js rewrite, new backend worker, and changes to the schema/migration.
- Any credential value. If one is found, reference only file:line and credential type, recommend rotation, and stop.

## Git workflow

- Branch: `feat/demo-showcase-ready`.
- Match observed commits: `feat: ...`, `test: ...`, `docs: ...` (e.g. `ca1984a` is `feat: add correction faq opt-out and health controls`).
- Commit checkpoints: (1) fixture reviewer identity/reset plus Python tests, (2) candidate/recruiter UI plus browser RED/GREEN tests, (3) keyboard/mobile coverage and docs.
- Do not push or open a PR without separate authorization. If later authorized, stage explicit in-scope paths only, push `feat/demo-showcase-ready`, and open one focused PR with exact verification output.

## Steps

### Step 1: Establish a server-owned fixture recruiter boundary and repeatable reset (RED → GREEN → REFACTOR)

1. First add focused Python tests using the existing server-thread/request helpers. Prove that a client cannot choose the human actor by supplying `actorType`/`actorId`, that a fixture recruiter disposition requires a nonempty reason, and that reset recreates only the selected fixture SQLite database with seeded data.
2. Run those tests and observe RED failures against the current request-controlled actor fields/no reset option.
3. Update `apps/api/server.py` and `apps/api/applications.py` so fixture disposition records a clearly labelled server-owned demo recruiter identity and ignores/rejects client attempts to impersonate actor identity. This is a controlled-demo boundary, not production auth.
4. Add a narrowly bounded reset option in `apps/api/__main__.py`. It may affect only the explicit local SQLite demo file supplied by `--db`; reject paths/backends outside the documented fixture boundary.
5. Run focused tests, then `python -m pytest -q --basetemp .pytest-temp`.

**Verify**: tests show reasonless disposition is rejected, request identity cannot become audit identity, and reset produces a fresh seeded SQLite demo.

### Step 2: Complete the browser candidate and recruiter story (RED → GREEN → REFACTOR)

1. Add the browser harness and a first failing desktop test. The test must submit a passing candidate, show evidence-based results, select/confirm a slot, reschedule it, switch to Recruiter, open the candidate record, record a reasoned disposition, and see analytics/final disposition update.
2. Run the focused browser test and confirm RED because controls and rendering do not exist.
3. In `web/index.html`, add labelled recruiter disposition controls and an analytics/funnel region. Preserve the candidate/recruiter boundary and do not add a client field that claims arbitrary actor identity.
4. In `web/app.js`, call existing detail, disposition, scheduling, and analytics endpoints; render evidence, evaluations, interviews, messages/work/audit records, disposition reason, and funnel values through `escapeHtml`. Refresh pipeline/analytics after state changes. All request errors must be visible to the operator.
5. In `web/styles.css`, use the existing token/focus pattern; keep candidate controls readable at narrow widths and do not rely only on color for state.
6. Run the focused browser test GREEN, then the full Python and browser suites.

**Verify**: the browser completes the primary candidate-to-recruiter workflow without an API client/curl fallback and shows the human-recorded disposition in the detail and analytics surfaces.

### Step 3: Make keyboard and responsive verification executable (RED → GREEN → REFACTOR)

1. Add failing Playwright tests for keyboard-only Candidate/Recruiter switching, focus-visible critical actions, form submission/handoff/scheduling controls, and the candidate primary flow at 320px width without horizontal page overflow.
2. Correct the tab implementation in `web/index.html`/`web/app.js`: either implement a complete tab pattern (stable IDs, `aria-controls`, panels, arrow/Home/End behavior, focus management) or replace the roles with simpler semantically correct navigation. Do not leave a partial ARIA tab pattern.
3. Make only minimal responsive CSS changes needed to pass the 320px assertions. Recruiter tables may use a labelled local scroll wrapper; the candidate primary flow may not cause document-level horizontal scrolling.
4. Run the focused tests then `cd web; npm run e2e`.

**Verify**: browser tests pass at desktop and 320px; keyboard users can reach and activate all critical candidate/recruiter actions with a visible focus indicator.

### Step 4: Document fixture deployment and demo operation after verification

1. Update `README.md`, `RUNBOOK.md`, `DEMO_SCRIPT.md`, `deployment.md`, `.env.example`, and `ACCEPTANCE_MATRIX.md` only after all behavior gates are green.
2. State `8104` as the showcase port and include prerequisites, no-secret fixture environment, reset/start/health/shutdown commands, desktop/mobile/keyboard browser verification, exact talk track, expected results, and fixture/live/provider boundary.
3. Mark browser/keyboard/mobile entries verified only when fresh command output exists. State that the static UI has no compile build step and that `npm run e2e` is the frontend gate.
4. Run the documented sequence from a clean shell and check the intended diff.

**Verify**: `python -m pytest -q --basetemp .pytest-temp`; `cd web; npm ci; npx playwright install chromium; npm run e2e`; `git diff --check`; `git status --short` shows only in-scope intended changes.

## Test plan

- New/updated Python tests: fixture server identity wins over request fields; reason is mandatory; reset is bounded/idempotent; health reports fixture readiness.
- New Playwright desktop trace: candidate application, explicit results, slot confirmation, reschedule, recruiter evidence, human disposition, analytics.
- New Playwright mobile/keyboard trace: 320px candidate flow, no document overflow, focus-visible critical controls, navigation and action activation without mouse.
- Existing suites remain the structural pattern: `tests/test_local_api.py` for server lifecycle and `tests/test_phase3_scheduling.py` for schedule/reschedule semantics.

## Done criteria

- [ ] `python -m apps.api --db .local/demo.sqlite3 --port 8104` and `/health` establish fixture-ready local launch.
- [ ] Reset is repeatable, limited to explicitly selected local fixture SQLite data, and verified by tests.
- [ ] Browser UI completes candidate application, screening, handoff/exception visibility, slot confirmation/rescheduling, recruiter evidence, final disposition with reason, and funnel analytics.
- [ ] The server—not client request fields—selects the recorded fixture reviewer identity.
- [ ] Browser coverage executes desktop, 320px, and keyboard-only critical flows.
- [ ] `python -m pytest -q --basetemp .pytest-temp` and `cd web; npm run e2e` pass.
- [ ] Documentation covers prerequisites, port, startup, health, reset, verification, talk track, fixture/live boundary, and shutdown; it does not claim live provider or production validation.
- [ ] No files outside Scope changed and `plans/README.md` is updated after approved review.

## STOP conditions

- The drift check or focused RED test shows the current route/model contract differs materially from this plan.
- A reset operation would delete a non-fixture database, permits an unresolved path, or requires a migration change.
- A complete human-review boundary requires production auth/hosted Supabase rather than the documented server-owned fixture actor; report the decision rather than claiming it is production security.
- Browser tooling cannot be committed with a lockfile or cannot start the local server deterministically.
- Any live provider credential, external service, schema/migration change, or out-of-scope file becomes necessary.
- A focused test cannot be made to fail for the named behavior, or a verification gate fails twice after a reasonable minimal correction.

## Maintenance notes

- Future live authentication must replace—not coexist ambiguously with—the fixture reviewer identity; review that boundary before enabling an external listener.
- Keep browser tests fixture-only and deterministic. Any provider outage simulation should remain visibly labelled and must not be represented as a live integration.
- Reviewers should scrutinize server-side actor attribution, no-horizontal-overflow assertions, and whether the UI renders the same records returned by the API.
