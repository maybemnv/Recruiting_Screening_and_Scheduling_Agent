"""Small server-side Supabase REST store.

The service-role key is accepted only by this server-side boundary.  The
browser uses the HTTP API and never talks to Supabase directly.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class SupabaseStoreError(RuntimeError):
    """Raised when Supabase cannot complete a persistence operation."""


class SupabaseStore:
    """PostgREST implementation of the requirement-store interface."""

    def __init__(self, rest_url: str, service_role_key: str):
        self.rest_url = rest_url.rstrip("/")
        self._service_role_key = service_role_key

    def close(self) -> None:
        """Match the SQLite store lifecycle; urllib has no persistent handle."""

    def _request(
        self,
        method: str,
        table: str,
        *,
        query: Mapping[str, str] | None = None,
        payload: object | None = None,
        prefer: str | None = None,
    ) -> list[dict[str, Any]]:
        url = f"{self.rest_url}/{table}"
        if query:
            url = f"{url}?{urlencode(query)}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "apikey": self._service_role_key,
            "Authorization": f"Bearer {self._service_role_key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        request = Request(url, data=body, method=method, headers=headers)
        try:
            with urlopen(request, timeout=15) as response:
                raw = response.read()
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise SupabaseStoreError(
                f"Supabase {method} {table} failed with HTTP {error.code}: {detail}"
            ) from error
        except URLError as error:
            raise SupabaseStoreError(f"Supabase {method} {table} unavailable") from error
        if not raw:
            return []
        decoded = json.loads(raw.decode("utf-8"))
        if not isinstance(decoded, list):
            raise SupabaseStoreError(f"Supabase {method} {table} returned an invalid response")
        return decoded

    def insert_job(self, job_id: str, slug: str, title: str) -> None:
        self._request(
            "POST",
            "jobs",
            payload={"id": job_id, "slug": slug, "title": title},
            prefer="return=minimal",
        )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        rows = self._request("GET", "jobs", query={"id": f"eq.{job_id}", "limit": "1"})
        return rows[0] if rows else None

    def get_job_by_slug(self, slug: str) -> dict[str, Any] | None:
        rows = self._request("GET", "jobs", query={"slug": f"eq.{slug}", "limit": "1"})
        return rows[0] if rows else None

    def list_jobs(self) -> list[dict[str, Any]]:
        return self._request("GET", "jobs", query={"order": "title.asc"})

    def next_version_number(self, job_id: str) -> int:
        rows = self._request(
            "GET",
            "requirement_versions",
            query={"job_id": f"eq.{job_id}", "order": "version.desc", "limit": "1"},
        )
        return int(rows[0]["version"]) + 1 if rows else 1

    def insert_requirement_version(
        self,
        version_id: str,
        job_id: str,
        version: int,
        payload: list[dict[str, Any]],
    ) -> None:
        self._request(
            "POST",
            "requirement_versions",
            payload={"id": version_id, "job_id": job_id, "version": version},
            prefer="return=minimal",
        )
        self._request(
            "POST",
            "criteria",
            payload={"version_id": version_id, "payload": payload},
            prefer="return=minimal",
        )

    def update_criteria(self, version_id: str, payload: list[dict[str, Any]]) -> None:
        self._request(
            "PATCH",
            "criteria",
            query={"version_id": f"eq.{version_id}"},
            payload={"payload": payload},
            prefer="return=minimal",
        )

    def get_requirement_version(self, version_id: str) -> dict[str, Any] | None:
        rows = self._request(
            "GET",
            "requirement_versions",
            query={"id": f"eq.{version_id}", "limit": "1"},
        )
        return rows[0] if rows else None

    def get_criteria(self, version_id: str) -> list[dict[str, Any]]:
        rows = self._request(
            "GET", "criteria", query={"version_id": f"eq.{version_id}", "limit": "1"}
        )
        if not rows:
            raise KeyError(f"Unknown requirement version: {version_id}")
        payload = rows[0]["payload"]
        if not isinstance(payload, list):
            raise SupabaseStoreError("Supabase criteria payload is not an array")
        return payload

    def publish_requirement_version(self, version_id: str) -> None:
        self._request(
            "PATCH",
            "requirement_versions",
            query={"id": f"eq.{version_id}"},
            payload={"status": "published", "published_at": "now()"},
            prefer="return=minimal",
        )

    def get_latest_published(self, job_id: str) -> dict[str, Any] | None:
        rows = self._request(
            "GET",
            "requirement_versions",
            query={
                "job_id": f"eq.{job_id}",
                "status": "eq.published",
                "order": "version.desc",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    def list_requirement_versions(self, job_id: str) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "requirement_versions",
            query={"job_id": f"eq.{job_id}", "order": "version.desc"},
        )
