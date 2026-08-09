"""Dependency-free HTTP surface for the local recruiting demo."""

from __future__ import annotations

import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .requirements import ImmutableVersionError, RequirementError, RequirementService
from .retail_fixture import seed_retail_job
from .storage import SQLiteStore


class RequestError(ValueError):
    """A client error that can be returned without exposing a traceback."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


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


def _version_payload(version: object) -> dict[str, object]:
    return {
        "id": version.id,
        "jobId": version.job_id,
        "version": version.version,
        "status": version.status,
        "publishedAt": version.published_at,
        "criteria": [criterion.to_mapping() for criterion in version.criteria],
    }


def create_demo_server(db_path: str | Path, port: int = 0) -> ThreadingHTTPServer:
    """Create a seeded local server with no external provider dependencies."""

    store = SQLiteStore(db_path)
    service = RequirementService(store)
    seed_retail_job(service)

    class DemoHandler(BaseHTTPRequestHandler):
        _web_root = Path(__file__).parents[2] / "web"

        def _json(self, status: int, payload: object) -> None:
            encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _error(self, status: int, code: str, message: str) -> None:
            self._json(status, {"code": code, "message": message})

        def _read_json(self) -> dict[str, object]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                payload = {} if not raw else json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
                raise RequestError(400, "INVALID_JSON", "Request body must be valid JSON") from error
            if not isinstance(payload, dict):
                raise RequestError(400, "INVALID_JSON", "JSON request body must be an object")
            return payload

        @staticmethod
        def _criteria(payload: dict[str, object]) -> list[dict[str, object]]:
            criteria = payload.get("criteria")
            if not isinstance(criteria, list):
                raise RequestError(422, "INVALID_CRITERIA", "criteria must be a list")
            return criteria

        def _file(self, name: str, content_type: str) -> None:
            path = self._web_root / name
            if not path.is_file():
                self._error(404, "NOT_FOUND", "Asset not found")
                return
            encoded = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        @staticmethod
        def _version_route(path: str) -> tuple[str, str | None, str | None] | None:
            prefix = "/api/jobs/"
            if not path.startswith(prefix):
                return None
            parts = path[len(prefix) :].split("/")
            if len(parts) == 2 and parts[1] == "requirement-versions":
                return parts[0], None, None
            if len(parts) == 3 and parts[1] == "requirement-versions":
                return parts[0], None, parts[2]
            if (
                len(parts) == 4
                and parts[1] == "requirement-versions"
                and parts[2]
            ):
                return parts[0], parts[2], parts[3]
            return None

        @staticmethod
        def _key_message(error: KeyError) -> str:
            return str(error.args[0]) if error.args else str(error)

        def _handle_error(self, error: Exception) -> None:
            if isinstance(error, RequestError):
                self._error(error.status, error.code, error.message)
            elif isinstance(error, ImmutableVersionError):
                self._error(409, "IMMUTABLE_VERSION", str(error))
            elif isinstance(error, KeyError):
                self._error(404, "NOT_FOUND", self._key_message(error))
            elif isinstance(error, RequirementError):
                self._error(422, "INVALID_CRITERIA", str(error))
            elif isinstance(error, sqlite3.IntegrityError):
                self._error(409, "CONFLICT", "The requested requirement version conflicts with existing state")
            else:
                self._error(400, "INVALID_REQUEST", str(error))

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            try:
                if path in {"/", "/index.html"}:
                    self._file("index.html", "text/html; charset=utf-8")
                    return
                if path == "/tokens.css":
                    self._file("tokens.css", "text/css; charset=utf-8")
                    return
                if path == "/styles.css":
                    self._file("styles.css", "text/css; charset=utf-8")
                    return
                if path == "/app.js":
                    self._file("app.js", "text/javascript; charset=utf-8")
                    return

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
                    version_id = parse_qs(parsed.query).get("version", [None])[0]
                    preview = service.candidate_preview_for_job(job.id, version_id)
                    version = service.get_version(preview["requirementVersionId"])
                    self._json(
                        200,
                        {
                            "job": {
                                "id": job.id,
                                "slug": job.slug,
                                "title": job.title,
                            },
                            "requirementVersionId": version.id,
                            "version": version.version,
                            "questions": preview["questions"],
                        },
                    )
                    return

                history_suffix = "/requirements/history"
                recruiter_prefix = "/api/recruiter/jobs/"
                if path.startswith(recruiter_prefix) and path.endswith(history_suffix):
                    job_id = path[len(recruiter_prefix) : -len(history_suffix)]
                    self._json(
                        200,
                        {
                            "job": _job_payload(service, job_id),
                            "versions": [
                                _version_payload(version)
                                for version in service.list_versions(job_id)
                            ],
                        },
                    )
                    return

                requirements_suffix = "/requirements"
                if path.startswith(recruiter_prefix) and path.endswith(requirements_suffix):
                    job_id = path[len(recruiter_prefix) : -len(requirements_suffix)]
                    job = service.get_job(job_id)
                    version = service.get_published_version(job.id)
                    self._json(
                        200,
                        {
                            "job": _job_payload(service, job.id),
                            "requirementVersionId": version.id,
                            "version": version.version,
                            "criteria": [
                                criterion.to_mapping() for criterion in version.criteria
                            ],
                        },
                    )
                    return

                version_route = self._version_route(path)
                if version_route is not None:
                    job_id, version_id, action = version_route
                    if version_id is None and action is None:
                        self._json(
                            200,
                            {
                                "jobId": job_id,
                                "versions": [
                                    _version_payload(version)
                                    for version in service.list_versions(job_id)
                                ],
                            },
                        )
                        return
                    if version_id is not None and action is None:
                        version = service.get_version(version_id)
                        if version.job_id != job_id:
                            raise KeyError(f"Unknown requirement version: {version_id}")
                        self._json(200, _version_payload(version))
                        return

                self._error(404, "NOT_FOUND", "Route not found")
            except Exception as error:  # noqa: BLE001 - convert all client errors to JSON
                self._handle_error(error)

        def _validate_payload(self, payload: dict[str, object]) -> dict[str, object]:
            normalized = service.validate_criteria(self._criteria(payload))
            return {
                "valid": True,
                "criteria": [criterion.to_mapping() for criterion in normalized],
            }

        def _replace_criteria(self, path: str) -> None:
            version_route = self._version_route(path)
            if version_route is None:
                self._error(404, "NOT_FOUND", "Route not found")
                return
            job_id, version_id, action = version_route
            if version_id is None or action != "criteria":
                self._error(404, "NOT_FOUND", "Route not found")
                return
            payload = self._read_json()
            version = service.get_version(version_id)
            if version.job_id != job_id:
                raise KeyError(f"Unknown requirement version: {version_id}")
            self._json(200, _version_payload(service.replace_criteria(version_id, self._criteria(payload))))

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
            path = urlparse(self.path).path.rstrip("/") or "/"
            try:
                collection_validate = "/api/jobs/"
                if path.startswith(collection_validate) and path.endswith(
                    "/requirement-versions/validate"
                ):
                    payload = self._read_json()
                    self._json(200, self._validate_payload(payload))
                    return

                version_route = self._version_route(path)
                if version_route is not None:
                    job_id, version_id, action = version_route
                    if version_id is None and action is None:
                        payload = self._read_json()
                        criteria = self._criteria(payload)
                        requested_id = payload.get("versionId", payload.get("id"))
                        if requested_id is not None and not isinstance(requested_id, str):
                            raise RequestError(422, "INVALID_REQUEST", "versionId must be a string")
                        version = service.create_draft(job_id, criteria, version_id=requested_id)
                        self._json(201, _version_payload(version))
                        return

                    if version_id is not None and action == "criteria":
                        self._replace_criteria(path)
                        return

                    if version_id is not None and action == "validate":
                        payload = self._read_json()
                        version = service.get_version(version_id)
                        if version.job_id != job_id:
                            raise KeyError(f"Unknown requirement version: {version_id}")
                        if "criteria" in payload:
                            result = self._validate_payload(payload)
                            result["requirementVersionId"] = version_id
                            self._json(200, result)
                        else:
                            validated = service.validate_version(version_id)
                            self._json(
                                200,
                                {
                                    "valid": True,
                                    "requirementVersionId": version_id,
                                    "criteria": [
                                        criterion.to_mapping()
                                        for criterion in validated.criteria
                                    ],
                                },
                            )
                        return

                    if version_id is not None and action == "publish":
                        version = service.get_version(version_id)
                        if version.job_id != job_id:
                            raise KeyError(f"Unknown requirement version: {version_id}")
                        self._json(200, _version_payload(service.publish(version_id)))
                        return

                self._error(404, "NOT_FOUND", "Route not found")
            except Exception as error:  # noqa: BLE001 - convert all client errors to JSON
                self._handle_error(error)

        def do_PUT(self) -> None:  # noqa: N802 - stdlib handler API
            try:
                self._replace_criteria(urlparse(self.path).path.rstrip("/") or "/")
            except Exception as error:  # noqa: BLE001 - convert all client errors to JSON
                self._handle_error(error)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), DemoHandler)
    server.demo_store = store  # type: ignore[attr-defined]
    return server
