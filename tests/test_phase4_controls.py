import json
import threading
from contextlib import contextmanager
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from apps.api.server import create_demo_server


@contextmanager
def running_demo(tmp_path):
    server = create_demo_server(tmp_path / "controls.sqlite3")
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


def payload():
    return {
        "contact": {"name": "Correction Candidate", "email": "correction@example.com"},
        "consent": {"sms": "granted", "email": "denied"},
        "resume": {"status": "complete", "fileId": "resume-controls"},
        "answers": {
            "work_authorization": True,
            "availability": "Sometimes, maybe weekends",
            "location": "Chicago",
            "experience": 3,
            "interview_slot": {"slotId": "slot-001"},
        },
    }


def create_review_application(base_url):
    status, application = request_json(
        f"{base_url}/api/apply/retail-operations/applications",
        method="POST",
        payload=payload(),
    )
    assert status == 201
    status, screened = request_json(
        f"{base_url}/api/applications/{application['id']}/screen",
        method="POST",
    )
    assert status == 200
    assert screened["nextAction"] == "review"
    return application


def test_candidate_correction_is_stored_and_force_rerun_uses_new_evidence(tmp_path):
    with running_demo(tmp_path) as base_url:
        application = create_review_application(base_url)
        status, corrected = request_json(
            f"{base_url}/api/applications/{application['id']}/answers",
            method="POST",
            payload={"criterionId": "availability", "value": ["weekends"]},
        )
        assert status == 200
        assert corrected["status"] == "review"

        status, rerun = request_json(
            f"{base_url}/api/applications/{application['id']}/screen",
            method="POST",
            payload={"forceRerun": True, "idempotencyKey": "screen:correction:2"},
        )
        assert status == 200
        results = {item["criterionId"]: item for item in rerun["results"]}
        assert results["availability"]["result"] == "pass"

        status, detail = request_json(
            f"{base_url}/api/recruiter/applications/{application['id']}"
        )
        assert status == 200
        assert any(item["extractionStatus"] == "corrected" for item in detail["evidence"])
        assert any(event["action"] == "candidate_answer_corrected" for event in detail["auditEvents"])


def test_faq_boundary_distinguishes_approved_answer_from_unsupported_question(tmp_path):
    with running_demo(tmp_path) as base_url:
        status, faqs = request_json(f"{base_url}/api/apply/retail-operations/faqs")
        assert status == 200
        assert faqs["faqs"]
        faq_id = faqs["faqs"][0]["id"]

        status, answer = request_json(
            f"{base_url}/api/apply/retail-operations/faqs/{faq_id}"
        )
        assert status == 200
        assert answer["approved"] is True

        status, unsupported = request_json(
            f"{base_url}/api/apply/retail-operations/faqs/not-approved"
        )
        assert status == 404
        assert unsupported["code"] == "FAQ_NOT_APPROVED"


def test_opt_out_suppresses_reminder_and_health_labels_fixture_capabilities(tmp_path):
    with running_demo(tmp_path) as base_url:
        application = create_review_application(base_url)
        status, _ = request_json(
            f"{base_url}/api/applications/{application['id']}/answers",
            method="POST",
            payload={"criterionId": "availability", "value": ["weekends"]},
        )
        assert status == 200
        status, _ = request_json(
            f"{base_url}/api/applications/{application['id']}/screen",
            method="POST",
            payload={"forceRerun": True},
        )
        assert status == 200
        status, _ = request_json(
            f"{base_url}/api/applications/{application['id']}/interviews",
            method="POST",
            payload={"slotId": "slot-001", "channel": "sms"},
        )
        assert status == 200

        status, _ = request_json(
            f"{base_url}/api/applications/{application['id']}/opt-out",
            method="POST",
            payload={"channel": "sms"},
        )
        assert status == 200
        status, reminder = request_json(
            f"{base_url}/api/applications/{application['id']}/reminders",
            method="POST",
            payload={"channel": "sms"},
        )
        assert status == 200
        assert reminder["message"]["status"] == "suppressed"
        assert reminder["message"]["providerResult"] == "consent_not_granted"

        status, health = request_json(f"{base_url}/api/integrations/health")
        assert status == 200
        assert health["calendar"]["mode"] == "fixture"
        assert health["ats"]["status"] == "blocked"
