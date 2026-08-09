import json
import threading
from contextlib import contextmanager
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from apps.api.server import create_demo_server


@contextmanager
def running_demo(tmp_path):
    server = create_demo_server(tmp_path / "phase2.sqlite3")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield base_url
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
        server.demo_store.close()


def request_json(url: str, method: str = "GET", payload: object | None = None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body else {},
    )
    try:
        with urlopen(request) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def passing_application_payload():
    return {
        "contact": {
            "name": "Jordan Lee",
            "email": "jordan@example.com",
            "phone": "+1-312-555-0100",
        },
        "consent": {"sms": "granted", "email": "denied"},
        "resume": {"status": "complete", "fileId": "resume-pass-001"},
        "answers": {
            "work_authorization": True,
            "availability": ["weekends", "Saturday 09:00-17:00"],
            "location": "Chicago",
            "experience": 3,
            "interview_slot": {
                "slotId": "slot-001",
                "startAt": "2026-08-14T10:00:00-05:00",
                "timeZone": "America/Chicago",
            },
        },
    }


def test_application_screening_is_versioned_evidenced_and_idempotent(tmp_path):
    with running_demo(tmp_path) as base_url:
        status, application = request_json(
            f"{base_url}/api/apply/retail-operations/applications",
            method="POST",
            payload=passing_application_payload(),
        )
        assert status == 201
        assert application["requirementVersionId"] == "retail-job-v1"
        assert application["status"] == "in_progress"
        application_id = application["id"]

        status, screened = request_json(
            f"{base_url}/api/applications/{application_id}/screen",
            method="POST",
            payload={"idempotencyKey": f"screen:{application_id}:retail-job-v1"},
        )
        assert status == 200
        assert screened["requirementVersionId"] == "retail-job-v1"
        assert [item["criterionId"] for item in screened["results"]] == [
            "work_authorization",
            "availability",
            "location",
            "experience",
            "interview_slot",
        ]
        assert [item["result"] for item in screened["results"]] == [
            "pass",
            "pass",
            "pass",
            "pass",
            "pass",
        ]
        assert screened["nextAction"] == "ready_to_schedule"

        status, replay = request_json(
            f"{base_url}/api/applications/{application_id}/screen",
            method="POST",
            payload={"idempotencyKey": f"screen:{application_id}:retail-job-v1"},
        )
        assert status == 200
        assert replay == screened

        status, detail = request_json(
            f"{base_url}/api/recruiter/applications/{application_id}"
        )
        assert status == 200
        assert detail["status"] == "ready_to_schedule"
        assert len(detail["evidence"]) == 6
        assert all(item["requirementVersionId"] == "retail-job-v1" for item in detail["evaluations"])
        assert all(item["evidenceIds"] for item in detail["evaluations"])
        assert {event["action"] for event in detail["auditEvents"]} >= {
            "application_created",
            "screening_evaluated",
        }

        status, pipeline = request_json(
            f"{base_url}/api/recruiter/jobs/retail-job/pipeline"
        )
        assert status == 200
        assert pipeline["counts"]["ready_to_schedule"] == 1
        assert pipeline["rows"][0]["id"] == application_id


def test_unreadable_resume_and_ambiguous_answer_route_to_review_and_handoff(tmp_path):
    payload = passing_application_payload()
    payload["answers"]["availability"] = "Sometimes, maybe weekends"
    del payload["answers"]["experience"]
    payload["resume"] = {"status": "unavailable", "fileId": "resume-unreadable-001"}

    with running_demo(tmp_path) as base_url:
        status, application = request_json(
            f"{base_url}/api/apply/retail-operations/applications",
            method="POST",
            payload=payload,
        )
        assert status == 201

        status, screened = request_json(
            f"{base_url}/api/applications/{application['id']}/screen",
            method="POST",
        )
        assert status == 200
        results = {item["criterionId"]: item for item in screened["results"]}
        assert results["availability"]["result"] == "review"
        assert results["experience"]["result"] == "review"
        assert screened["nextAction"] == "review"

        status, detail = request_json(
            f"{base_url}/api/recruiter/applications/{application['id']}"
        )
        assert status == 200
        assert detail["resume"]["status"] == "unavailable"
        assert any(item["kind"] == "human_handoff" for item in detail["workItems"])

        status, handoff = request_json(
            f"{base_url}/api/applications/{application['id']}/handoff",
            method="POST",
            payload={"reason": "candidate_requested_human"},
        )
        assert status == 200
        assert handoff["status"] == "human_handoff"

        status, paused = request_json(
            f"{base_url}/api/applications/{application['id']}/screen",
            method="POST",
        )
        assert status == 200
        assert paused["nextAction"] == "human_handoff"


def test_agent_cannot_create_final_disposition_and_recruiter_reason_is_required(tmp_path):
    with running_demo(tmp_path) as base_url:
        status, application = request_json(
            f"{base_url}/api/apply/retail-operations/applications",
            method="POST",
            payload=passing_application_payload(),
        )
        assert status == 201
        application_id = application["id"]

        status, blocked = request_json(
            f"{base_url}/api/applications/{application_id}/disposition",
            method="POST",
            payload={"actorType": "agent", "disposition": "advance", "reason": "pass"},
        )
        assert status == 403
        assert blocked["code"] == "HUMAN_ACTOR_REQUIRED"

        status, missing_reason = request_json(
            f"{base_url}/api/applications/{application_id}/disposition",
            method="POST",
            payload={"actorType": "recruiter", "disposition": "advance"},
        )
        assert status == 409
        assert missing_reason["code"] == "HUMAN_REASON_REQUIRED"

        status, dispositioned = request_json(
            f"{base_url}/api/applications/{application_id}/disposition",
            method="POST",
            payload={
                "actorType": "recruiter",
                "actorId": "recruiter-demo",
                "disposition": "advance",
                "reason": "Reviewed the explicit evidence before advancing.",
            },
        )
        assert status == 200
        assert dispositioned["status"] == "dispositioned"
