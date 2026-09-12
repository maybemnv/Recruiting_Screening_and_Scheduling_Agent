import json
import threading
from copy import deepcopy
from contextlib import contextmanager
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from apps.api.server import create_demo_server
from apps.api.retail_fixture import load_retail_fixture


@contextmanager
def running_demo(tmp_path):
    server = create_demo_server(tmp_path / "completion.sqlite3")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
        server.demo_store.close()


def request_json(url, method="GET", payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, method=method, headers={"Content-Type": "application/json"} if body else {})
    try:
        with urlopen(request) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def ready_application(base_url):
    payload = {
        "contact": {"name": "Fixture Candidate", "email": "fixture@example.com", "phone": "+15555550123"},
        "consent": {"sms": "granted", "email": "denied"},
        "resume": {"status": "complete", "fileId": "resume-completion"},
        "answers": {"work_authorization": True, "availability": ["weekends"], "location": "Chicago", "experience": 3, "interview_slot": {"slotId": "slot-001"}},
    }
    status, application = request_json(f"{base_url}/api/apply/retail-operations/applications", "POST", payload)
    assert status == 201
    status, _ = request_json(f"{base_url}/api/applications/{application['id']}/screen", "POST")
    assert status == 200
    status, _ = request_json(f"{base_url}/api/applications/{application['id']}/interviews", "POST", {"slotId": "slot-001", "channel": "sms"})
    assert status == 200
    return application["id"]


def test_fixture_reminder_recovery_retries_once_and_is_idempotent(tmp_path, monkeypatch):
    with running_demo(tmp_path) as base_url:
        application_id = ready_application(base_url)
        monkeypatch.setenv("RECRUITING_DEMO_MESSAGING_MODE", "outage")
        status, failed = request_json(f"{base_url}/api/applications/{application_id}/reminders", "POST", {"channel": "sms"})
        assert status == 503
        assert failed["code"] == "PROVIDER_DEGRADED"

        monkeypatch.setenv("RECRUITING_DEMO_MESSAGING_MODE", "fixture")
        status, recovered = request_json(f"{base_url}/api/applications/{application_id}/reminder-recovery", "POST", {"channel": "sms"})
        assert status == 200
        assert recovered["message"]["status"] == "sent"
        assert recovered["workItem"]["status"] == "recovered"
        assert recovered["workItem"]["attempts"] == 2

        status, replay = request_json(f"{base_url}/api/applications/{application_id}/reminder-recovery", "POST", {"channel": "sms"})
        assert status == 200
        assert replay == recovered


def test_fixture_ats_sync_pending_recovers_once_with_an_audit_event(tmp_path):
    with running_demo(tmp_path) as base_url:
        application_id = ready_application(base_url)
        status, pending = request_json(f"{base_url}/api/applications/{application_id}/ats-sync", "POST")
        assert status == 202
        assert pending["sync"]["status"] == "sync_pending"

        status, retried = request_json(f"{base_url}/api/applications/{application_id}/ats-sync", "POST", {"retry": True})
        assert status == 202
        assert retried["sync"]["status"] == "sync_pending"
        assert retried["sync"]["attempts"] == 1

        status, retry_rejected = request_json(f"{base_url}/api/applications/{application_id}/ats-sync", "POST", {"retry": True})
        assert status == 409
        assert retry_rejected["code"] == "FIXTURE_ATS_RETRY_LIMIT"
        status, detail = request_json(f"{base_url}/api/recruiter/applications/{application_id}")
        assert status == 200
        assert [
            (item["status"], item["attempts"])
            for item in detail["workItems"]
            if item["kind"] == "ats_sync"
        ] == [("sync_pending", 1)]

        status, recovered = request_json(f"{base_url}/api/applications/{application_id}/ats-sync", "POST", {"recover": True})
        assert status == 200
        assert recovered["sync"]["status"] == "synced"

        status, detail = request_json(f"{base_url}/api/recruiter/applications/{application_id}")
        assert status == 200
        assert [item["status"] for item in detail["workItems"] if item["kind"] == "ats_sync"] == ["synced"]
        assert [item["action"] for item in detail["auditEvents"]].count("fixture_ats_sync_recovered") == 1


def test_scorecard_and_synthetic_monitoring_keep_human_decisions_separate(tmp_path):
    with running_demo(tmp_path) as base_url:
        application_id = ready_application(base_url)
        status, scorecard = request_json(f"{base_url}/api/recruiter/applications/{application_id}/scorecard")
        assert status == 200
        assert scorecard["automatedResults"]
        assert scorecard["humanOverride"] is None
        assert scorecard["finalDisposition"] is None

        status, monitoring = request_json(f"{base_url}/api/recruiter/jobs/retail-job/monitoring")
        assert status == 200
        assert monitoring["synthetic"] is True
        assert monitoring["denominator"] == 1
        assert monitoring["limitations"]
        alert = monitoring["alerts"][0]
        assert alert["ownerId"] == "fixture-reviewer"
        assert alert["status"] == "open"

        status, investigating = request_json(f"{base_url}/api/recruiter/jobs/retail-job/monitoring/{alert['id']}", "POST", {"action": "investigate", "note": "Fixture data reviewed."})
        assert status == 200
        assert investigating["alert"]["status"] == "investigating"
        status, resolved = request_json(f"{base_url}/api/recruiter/jobs/retail-job/monitoring/{alert['id']}", "POST", {"action": "resolve", "note": "Synthetic limitation retained."})
        assert status == 200
        assert resolved["alert"]["status"] == "resolved"


def test_monitoring_refresh_updates_population_without_resetting_review_state(tmp_path):
    with running_demo(tmp_path) as base_url:
        ready_application(base_url)
        status, first = request_json(f"{base_url}/api/recruiter/jobs/retail-job/monitoring")
        assert status == 200
        alert = first["alerts"][0]
        status, investigated = request_json(
            f"{base_url}/api/recruiter/jobs/retail-job/monitoring/{alert['id']}",
            "POST",
            {"action": "investigate", "note": "Review in progress."},
        )
        assert status == 200
        assert investigated["alert"]["status"] == "investigating"

        ready_application(base_url)
        status, refreshed = request_json(f"{base_url}/api/recruiter/jobs/retail-job/monitoring")
        assert status == 200
        assert refreshed["denominator"] == 2
        refreshed_alert = refreshed["alerts"][0]
        assert refreshed_alert["denominator"] == 2
        assert refreshed_alert["status"] == "investigating"
        assert refreshed_alert["note"] == "Review in progress."


def test_ac07_force_rerun_adopts_latest_published_version_only_after_normal_replay(tmp_path):
    with running_demo(tmp_path) as base_url:
        application_id = ready_application(base_url)
        status, before_publish = request_json(
            f"{base_url}/api/recruiter/applications/{application_id}"
        )
        assert status == 200
        v1_evaluation_ids = [item["id"] for item in before_publish["evaluations"]]
        assert before_publish["requirementVersionId"] == "retail-job-v1"
        criteria = deepcopy(load_retail_fixture()["requirementVersion"]["criteria"])
        criteria[0]["candidateQuestion"] = "Updated v2 wording"
        status, draft = request_json(
            f"{base_url}/api/jobs/retail-job/requirement-versions", "POST", {"criteria": criteria}
        )
        assert status == 201
        status, published = request_json(
            f"{base_url}/api/jobs/retail-job/requirement-versions/{draft['id']}/publish", "POST"
        )
        assert status == 200
        assert published["id"] != "retail-job-v1"

        status, unchanged = request_json(f"{base_url}/api/applications/{application_id}/screen", "POST")
        assert status == 200
        assert unchanged["requirementVersionId"] == "retail-job-v1"
        assert [item["id"] for item in unchanged["results"]] == v1_evaluation_ids

        status, rescreened = request_json(
            f"{base_url}/api/applications/{application_id}/screen", "POST", {"forceRerun": True}
        )
        assert status == 200
        assert rescreened["requirementVersionId"] == published["id"]
        assert all(item["requirementVersionId"] == published["id"] for item in rescreened["results"])
        status, detail = request_json(f"{base_url}/api/recruiter/applications/{application_id}")
        assert status == 200
        assert detail["requirementVersionId"] == published["id"]
        assert all(item["requirementVersionId"] == published["id"] for item in detail["evaluations"])
