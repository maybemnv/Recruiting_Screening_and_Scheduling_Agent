"""Dependency-free HTTP surface for the local recruiting demo."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .requirements import RequirementService
from .retail_fixture import seed_retail_job
from .storage import SQLiteStore


def _job_payload(service: RequirementService, job_id: str) -> dict[str, object]:
    job = service.get_job(job_id)
    version = service.get_published_version(job.id)
    return {
        "id": job.id,
        "slug": job.slug,
        "title": job.title,
        "publishedVersionId": version.id,
        "publishedVersion": version.version,
    }


def create_demo_server(db_path: str | Path, port: int = 0) -> ThreadingHTTPServer:
    """Create a seeded local server with no external provider dependencies."""

    store = SQLiteStore(db_path)
    service = RequirementService(store)
    seed_retail_job(service)

    class DemoHandler(BaseHTTPRequestHandler):
        def _json(self, status: int, payload: object) -> None:
            encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            path = urlparse(self.path).path.rstrip("/") or "/"
            try:
                if path == "/health":
                    self._json(
                        200,
                        {
                            "status": "ok",
                            "mode": "fixture",
                            "providerDependencies": "none",
                        },
                    )
                    return

                if path == "/api/recruiter/jobs":
                    self._json(
                        200,
                        {"jobs": [_job_payload(service, job.id) for job in service.list_jobs()]},
                    )
                    return

                candidate_prefix = "/api/apply/"
                if path.startswith(candidate_prefix):
                    slug = path[len(candidate_prefix) :]
                    job = service.get_job_by_slug(slug)
                    version = service.get_published_version(job.id)
                    preview = service.candidate_preview(version.id)
                    self._json(
                        200,
                        {
                            "job": {
                                "id": job.id,
                                "slug": job.slug,
                                "title": job.title,
                            },
                            "requirementVersionId": version.id,
                            "questions": preview["questions"],
                        },
                    )
                    return

                recruiter_prefix = "/api/recruiter/jobs/"
                if path.startswith(recruiter_prefix) and path.endswith("/requirements"):
                    job_id = path[len(recruiter_prefix) : -len("/requirements")]
                    job = service.get_job(job_id)
                    version = service.get_published_version(job.id)
                    self._json(
                        200,
                        {
                            "job": _job_payload(service, job.id),
                            "requirementVersionId": version.id,
                            "criteria": [
                                criterion.to_mapping() for criterion in version.criteria
                            ],
                        },
                    )
                    return

                self._json(404, {"code": "NOT_FOUND", "message": "Route not found"})
            except KeyError as error:
                self._json(404, {"code": "NOT_FOUND", "message": str(error)})

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), DemoHandler)
    server.demo_store = store  # type: ignore[attr-defined]
    return server
