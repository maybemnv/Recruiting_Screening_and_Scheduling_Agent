import json
import threading
from contextlib import contextmanager
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from apps.api.replay import replay_retail_demo
from apps.api.server import create_demo_server


@contextmanager
def running_demo(tmp_path):
    server = create_demo_server(tmp_path / "phase4.sqlite3")
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


def application_payload(name: str, *, ambiguous: bool = False):
    return {
        "contact": {"name": name, "email": f"{name.lower().replace(' ', '.')}@example.com"},
        "consent": {"sms": "granted", "email": "denied"},
        "resume": {"status": "complete", "fileId": f"resume-{name}"},
        "answers": {
            "work_authorization": True,
            "availability": "Sometimes, maybe weekends" if ambiguous else ["weekends"],
            "location": "Chicago",
            "experience": 3,
            "interview_slot": {"slotId": "slot-001"},
        },
    }


def test_pipeline_filters_and_funnel_analytics_expose_denominators(tmp_path):
    with running_demo(tmp_path) as base_url:
        ids = []
        for name, ambiguous in (("Ready Candidate", False), ("Review Candidate", True)):
            status, application = request_json(
                f"{base_url}/api/apply/retail-operations/applications",
                method="POST",
                payload=application_payload(name, ambiguous=ambiguous),
            )
            assert status == 201
            ids.append(application["id"])
            status, screened = request_json(
                f"{base_url}/api/applications/{application['id']}/screen",
                method="POST",
            )
            assert status == 200
            if not ambiguous:
                status, _ = request_json(
                    f"{base_url}/api/applications/{application['id']}/interviews",
                    method="POST",
                    payload={"slotId": "slot-001", "channel": "sms"},
                )
                assert status == 200
            else:
                assert screened["nextAction"] == "review"

        status, scheduled = request_json(
            f"{base_url}/api/recruiter/jobs/retail-job/pipeline?status=scheduled"
        )
        assert status == 200
        assert [row["id"] for row in scheduled["rows"]] == [ids[0]]

        status, analytics = request_json(
            f"{base_url}/api/recruiter/jobs/retail-job/analytics"
        )
        assert status == 200
        assert analytics["denominator"] == 2
        assert analytics["stages"]["scheduled"] == 1
        assert analytics["stages"]["review"] == 1
        assert analytics["timestampDefinition"] == "applications.created_at"
        assert analytics["byRequirementVersion"]["retail-job-v1"] == 2
        assert analytics["missingness"]["applicationsWithoutEvaluation"] == 0


def test_retail_replay_reconciles_500_applications_and_five_evaluations_each(tmp_path):
    result = replay_retail_demo(tmp_path / "replay.sqlite3", count=500)

    assert result["applications"] == 500
    assert result["evaluations"] == 2500
    assert result["evidence"] == 3000
    assert result["funnelApplications"] == 500
    assert result["workItems"] == 50
    assert result["auditEvents"] > 500
    assert result["requirementVersionId"] == "retail-job-v1"
    assert result["reconciled"] is True
