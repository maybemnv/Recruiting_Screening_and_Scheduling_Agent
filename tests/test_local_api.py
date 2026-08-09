import json
import threading
from urllib.request import urlopen

from apps.api.server import create_demo_server


def test_local_api_exposes_recruiter_job_and_candidate_preview(tmp_path):
    server = create_demo_server(tmp_path / "demo.sqlite3")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        with urlopen(f"{base_url}/api/recruiter/jobs") as response:
            jobs = json.load(response)
        assert jobs["jobs"][0]["id"] == "retail-job"
        assert jobs["jobs"][0]["publishedVersionId"] == "retail-job-v1"

        with urlopen(f"{base_url}/api/apply/retail-operations") as response:
            application = json.load(response)
        assert application["job"]["slug"] == "retail-operations"
        assert application["requirementVersionId"] == "retail-job-v1"
        assert len(application["questions"]) == 5
        assert application["questions"][0]["criterionId"] == "work_authorization"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
        server.demo_store.close()
