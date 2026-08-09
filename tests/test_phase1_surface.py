import json
import threading
from urllib.request import Request, urlopen

from apps.api.retail_fixture import load_retail_fixture
from apps.api.server import create_demo_server


def _request_json(url: str, method: str = "GET", payload: object | None = None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body else {},
    )
    with urlopen(request) as response:
        return response.status, json.load(response)


def test_recruiter_can_publish_a_new_requirement_version_without_mutating_v1(tmp_path):
    server = create_demo_server(tmp_path / "demo.sqlite3")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        fixture = load_retail_fixture()
        criteria = fixture["requirementVersion"]["criteria"]
        criteria[0]["candidateQuestion"] = "Can you work in the job location?"

        status, draft = _request_json(
            f"{base_url}/api/jobs/retail-job/requirement-versions",
            method="POST",
            payload={"criteria": criteria},
        )
        assert status == 201
        assert draft["version"] == 2
        assert draft["status"] == "draft"

        _, before_publish = _request_json(
            f"{base_url}/api/recruiter/jobs/retail-job/requirements"
        )
        assert before_publish["requirementVersionId"] == "retail-job-v1"

        status, published = _request_json(
            f"{base_url}/api/jobs/retail-job/requirement-versions/{draft['id']}/publish",
            method="POST",
        )
        assert status == 200
        assert published["status"] == "published"

        _, after_publish = _request_json(
            f"{base_url}/api/recruiter/jobs/retail-job/requirements"
        )
        assert after_publish["requirementVersionId"] == draft["id"]
        assert after_publish["criteria"][0]["candidateQuestion"] == (
            "Can you work in the job location?"
        )

        _, old_preview = _request_json(
            f"{base_url}/api/apply/retail-operations?version=retail-job-v1"
        )
        assert old_preview["requirementVersionId"] == "retail-job-v1"
        assert old_preview["questions"][0]["question"] == (
            "Are you authorized to work in the job location?"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
        server.demo_store.close()


def test_demo_ui_serves_candidate_and_recruiter_surfaces(tmp_path):
    server = create_demo_server(tmp_path / "demo.sqlite3")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        with urlopen(f"{base_url}/") as response:
            html = response.read().decode("utf-8")
        with urlopen(f"{base_url}/tokens.css") as response:
            tokens = response.read().decode("utf-8")
        with urlopen(f"{base_url}/app.js") as response:
            script = response.read().decode("utf-8")

        assert "Recruiting Screening" in html
        assert "Candidate" in html
        assert "Recruiter" in html
        assert "resumeStatus" in html
        assert "pipeline-table" in html
        assert 'aria-live="polite"' in html
        assert "--brand-ink" in tokens
        assert "api/apply/retail-operations" in script
        assert "/api/applications/" in script
        assert "/reschedule" in script
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
        server.demo_store.close()
