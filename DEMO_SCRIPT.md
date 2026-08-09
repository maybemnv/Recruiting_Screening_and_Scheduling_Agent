# Retail recruiting client demo

## Start

From the repository root, use Python and the dependency-free local server:

```powershell
python -m pytest -q --basetemp .pytest-temp
python -m apps.api --db .local/demo.sqlite3 --port 8000
```

Open `http://127.0.0.1:8000/`. The page is a fixture shell; no login or real
candidate data is required. Reset between rehearsals by choosing a new SQLite
path such as `.local/demo-run-02.sqlite3`.

## Happy path

1. In Candidate, enter a name and email.
2. Answer yes to work authorization, enter weekend availability, enter
   Chicago, enter `3` years, and choose a slot.
3. Leave SMS consent enabled and choose a readable fixture resume.
4. Submit. Show the five ordered `pass`/`review` states and the published
   requirement version.
5. Confirm the Chicago-time-zone slot. Show the fixture confirmation record.
6. Switch to Recruiter. Open the pipeline row and show evidence, rule
   explanations, audit events, interview, and message records.
7. Use the recruiter API disposition only with a human actor and a reason.

## Exception path

1. Use `Resume status = Unreadable resume` and enter `Sometimes, maybe
   weekends` for availability.
2. Submit and show `review` for ambiguous availability and missing experience.
3. Select `Request human help`; show `human_handoff` and the queued work item.
4. For outage handling, stop the server and restart with:

   ```powershell
   $env:RECRUITING_DEMO_CALENDAR_MODE = "outage"
   python -m apps.api --db .local/demo-outage.sqlite3 --port 8000
   ```

   Booking returns visible provider degradation and a retryable work item; the
   application remains ready to schedule. Reset the variable to `fixture` for
   the happy path.
5. Book a slot, then choose another slot and use `Replace confirmed slot`.
   Show one active interview and the cancelled predecessor.
6. Replay the same callback payload twice at
   `POST /api/integrations/calendar/callback`; the second response is marked
   duplicate.

## Scale/reconciliation path

```powershell
python -m apps.api.replay --db .local/replay.sqlite3 --count 500
```

The output reports applications, five evaluations per application, evidence,
work items, audit events, funnel total, and a `reconciled` boolean.
