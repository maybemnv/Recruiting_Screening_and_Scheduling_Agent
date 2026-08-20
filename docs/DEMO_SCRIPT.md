# Retail recruiting client demo

## Start

From the repository root, use Python and the dependency-free local server:

```powershell
python -m pytest -q --basetemp .pytest-temp
python -m apps.api --db .local/demo.sqlite3 --reset --port 8104
```

Open `http://127.0.0.1:8104/`. The page is a fixture shell; no login or real
candidate data is required. The same reset command restores the deterministic
seed. Expected `/health` fields include `fixtureReady: true` and
`seededJobId: retail-job`.

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
7. Choose `Advance`, enter a reason, and select `Record human disposition`.
   Show the server-owned `fixture-recruiter` identity, audit trail, and the
   funnel analytics changing to one human-recorded final disposition.

## Exception path

1. Use `Resume status = Unreadable resume` and enter `Sometimes, maybe
   weekends` for availability.
2. Submit and show `review` for ambiguous availability and missing experience.
3. Select `Request human help`; show `human_handoff` and the queued work item.
4. For outage handling, stop the server and restart with:

   ```powershell
   $env:RECRUITING_DEMO_CALENDAR_MODE = "outage"
   python -m apps.api --db .local/demo-outage.sqlite3 --reset --port 8104
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

## Talk track and close

The rules and evidence are explicit; automation can screen and schedule, but
the final disposition is attributed to a labelled human fixture identity with
a required reason. ATS, calendar, SMS, and email calls are simulated; no live
provider or production-auth claim is made. Show keyboard tab switching and the
320px candidate layout if requested. Stop the server with `Ctrl+C`.
