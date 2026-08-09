import copy
import json
import threading
from contextlib import contextmanager
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from apps.api.retail_fixture import load_retail_fixture
from apps.api.server import create_demo_server


@contextmanager
def running_demo(tmp_path):
    server = create_demo_server(tmp_path / "demo.sqlite3")
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


def test_http_requirement_mutations_and_history_preserve_published_preview(tmp_path):
    fixture = load_retail_fixture()
    criteria = copy.deepcopy(fixture["requirementVersion"]["criteria"])
    criteria[0]["candidateQuestion"] = "Can you work in the job location?"

    with running_demo(tmp_path) as base_url:
        status, validation = request_json(
            f"{base_url}/api/jobs/retail-job/requirement-versions/validate",
            method="POST",
            payload={"criteria": criteria},
        )
        assert status == 200
        assert validation["valid"] is True

        status, draft = request_json(
            f"{base_url}/api/jobs/retail-job/requirement-versions",
            method="POST",
            payload={"criteria": criteria},
        )
        assert status == 201
        assert draft["version"] == 2
        assert draft["status"] == "draft"

        criteria[0]["candidateQuestion"] = "Can you work near the job location?"
        status, replaced = request_json(
            f"{base_url}/api/jobs/retail-job/requirement-versions/{draft['id']}/criteria",
            method="PUT",
            payload={"criteria": criteria},
        )
        assert status == 200
        assert replaced["criteria"][0]["candidateQuestion"] == (
            "Can you work near the job location?"
        )

        status, version_validation = request_json(
            f"{base_url}/api/jobs/retail-job/requirement-versions/{draft['id']}/validate",
            method="POST",
        )
        assert status == 200, version_validation
        assert version_validation["requirementVersionId"] == draft["id"]

        status, published = request_json(
            f"{base_url}/api/jobs/retail-job/requirement-versions/{draft['id']}/publish",
            method="POST",
        )
        assert status == 200
        assert published["status"] == "published"

        status, history = request_json(
            f"{base_url}/api/recruiter/jobs/retail-job/requirements/history"
        )
        assert status == 200
        assert [version["id"] for version in history["versions"]] == [
            draft["id"],
            "retail-job-v1",
        ]

        status, old_preview = request_json(
            f"{base_url}/api/apply/retail-operations?version=retail-job-v1"
        )
        assert status == 200
        assert old_preview["requirementVersionId"] == "retail-job-v1"
        assert old_preview["questions"][0]["question"] == (
            "Are you authorized to work in the job location?"
        )

        status, current_preview = request_json(
            f"{base_url}/api/apply/retail-operations"
        )
        assert status == 200
        assert current_preview["requirementVersionId"] == draft["id"]
        assert current_preview["questions"][0]["question"] == (
            "Can you work near the job location?"
        )


def test_http_rejects_invalid_criteria_and_immutable_mutations_as_json(tmp_path):
    fixture = load_retail_fixture()
    criteria = copy.deepcopy(fixture["requirementVersion"]["criteria"])
    criteria[0]["type"] = "unsupported_type"

    with running_demo(tmp_path) as base_url:
        status, invalid = request_json(
            f"{base_url}/api/jobs/retail-job/requirement-versions",
            method="POST",
            payload={"criteria": criteria},
        )
        assert status == 422
        assert invalid == {
            "code": "INVALID_CRITERIA",
            "message": "Unsupported criterion type: unsupported_type",
        }

        status, immutable = request_json(
            f"{base_url}/api/jobs/retail-job/requirement-versions/retail-job-v1/criteria",
            method="PUT",
            payload={"criteria": load_retail_fixture()["requirementVersion"]["criteria"]},
        )
        assert status == 409
        assert immutable["code"] == "IMMUTABLE_VERSION"

        status, draft_error = request_json(
            f"{base_url}/api/apply/retail-operations?version=retail-job-v1-missing"
        )
        assert status == 404
        assert draft_error["code"] == "NOT_FOUND"
