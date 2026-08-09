"""Deterministic retail replay for Phase 4 reconciliation checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .applications import ApplicationService
from .requirements import RequirementService
from .retail_fixture import seed_retail_job
from .storage import SQLiteStore


def replay_retail_demo(db_path: str | Path, count: int = 500) -> dict[str, Any]:
    if count < 1:
        raise ValueError("count must be positive")
    store = SQLiteStore(db_path)
    try:
        requirements = RequirementService(store)
        seed_retail_job(requirements)
        applications = ApplicationService(store, requirements)
        for index in range(1, count + 1):
            ambiguous = index % 10 == 0
            application = applications.create_application(
                "retail-operations",
                {
                    "contact": {
                        "name": f"Replay Candidate {index:03d}",
                        "email": f"replay-{index:03d}@example.com",
                    },
                    "consent": {"sms": "granted", "email": "denied"},
                    "resume": {"status": "complete", "fileId": f"replay-resume-{index:03d}"},
                    "answers": {
                        "work_authorization": True,
                        "availability": "Sometimes, maybe weekends" if ambiguous else ["weekends"],
                        "location": "Chicago",
                        "experience": 3,
                        "interview_slot": {"slotId": "slot-001"},
                    },
                },
            )
            applications.screen_application(application["id"], f"replay:{index}:retail-job-v1")

        application_rows = store.list_applications("retail-job")
        evaluation_count = sum(
            len(store.list_evaluations(row["id"])) for row in application_rows
        )
        evidence_count = sum(len(store.list_evidence(row["id"])) for row in application_rows)
        work_item_count = sum(len(store.list_work_items(row["id"])) for row in application_rows)
        audit_count = sum(
            len(store.list_audit_events("application", row["id"])) for row in application_rows
        )
        stage_counts: dict[str, int] = {}
        for row in application_rows:
            stage_counts[row["status"]] = stage_counts.get(row["status"], 0) + 1
        reconciled = (
            len(application_rows) == count
            and evaluation_count == count * 5
            and evidence_count == count * 6
            and sum(stage_counts.values()) == count
        )
        return {
            "applications": len(application_rows),
            "evaluations": evaluation_count,
            "evidence": evidence_count,
            "workItems": work_item_count,
            "interviews": 0,
            "messages": 0,
            "auditEvents": audit_count,
            "funnelApplications": sum(stage_counts.values()),
            "stages": stage_counts,
            "requirementVersionId": "retail-job-v1",
            "reconciled": reconciled,
        }
    finally:
        store.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay deterministic retail applications")
    parser.add_argument("--db", default=".local/replay.sqlite3")
    parser.add_argument("--count", type=int, default=500)
    args = parser.parse_args()
    print(json.dumps(replay_retail_demo(args.db, args.count), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
