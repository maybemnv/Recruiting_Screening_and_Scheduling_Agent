"""Small server-side Supabase REST store.

The service-role key is accepted only by this server-side boundary.  The
browser uses the HTTP API and never talks to Supabase directly.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
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
            payload={
                "status": "published",
                "published_at": datetime.now(timezone.utc).isoformat(),
            },
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

    def insert_application(
        self,
        application_id: str,
        job_id: str,
        requirement_version_id: str,
        contact: dict[str, Any],
        consent: dict[str, str],
        status: str,
        resume_status: str,
        resume_file_id: str | None,
    ) -> None:
        self._request(
            "POST",
            "applications",
            payload={
                "id": application_id,
                "job_id": job_id,
                "requirement_version_id": requirement_version_id,
                "contact": contact,
                "status": status,
                "consent": consent,
                "resume_status": resume_status,
                "resume_file_id": resume_file_id,
            },
            prefer="return=minimal",
        )

    def get_application(self, application_id: str) -> dict[str, Any] | None:
        rows = self._request(
            "GET", "applications", query={"id": f"eq.{application_id}", "limit": "1"}
        )
        return rows[0] if rows else None

    def list_applications(self, job_id: str) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "applications",
            query={"job_id": f"eq.{job_id}", "order": "created_at.asc,id.asc"},
        )

    def update_application(
        self,
        application_id: str,
        *,
        status: str | None = None,
        disposition: str | None = None,
        disposition_reason: str | None = None,
        dispositioned_by: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {}
        for key, value in (
            ("status", status),
            ("disposition", disposition),
            ("disposition_reason", disposition_reason),
            ("dispositioned_by", dispositioned_by),
        ):
            if value is not None:
                payload[key] = value
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._request(
            "PATCH",
            "applications",
            query={"id": f"eq.{application_id}"},
            payload=payload,
            prefer="return=minimal",
        )

    def insert_evidence(
        self,
        evidence_id: str,
        application_id: str,
        criterion_id: str | None,
        source: str,
        value: Any,
        source_reference: dict[str, Any],
        confidence: float | None,
        extraction_status: str,
    ) -> None:
        self._request(
            "POST",
            "evidence",
            payload={
                "id": evidence_id,
                "application_id": application_id,
                "criterion_id": criterion_id,
                "source": source,
                "value": value,
                "source_reference": source_reference,
                "confidence": confidence,
                "extraction_status": extraction_status,
            },
            prefer="return=minimal",
        )

    def list_evidence(self, application_id: str) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "evidence",
            query={
                "application_id": f"eq.{application_id}",
                "order": "created_at.asc,id.asc",
            },
        )

    def insert_evaluation(
        self,
        evaluation_id: str,
        application_id: str,
        requirement_version_id: str,
        criterion_id: str,
        result: str,
        evidence_ids: list[str],
        rule_expression: str,
        explanation: str,
        evaluator: str,
    ) -> None:
        self._request(
            "POST",
            "evaluations",
            payload={
                "id": evaluation_id,
                "application_id": application_id,
                "requirement_version_id": requirement_version_id,
                "criterion_id": criterion_id,
                "result": result,
                "evidence_ids": evidence_ids,
                "rule_expression": rule_expression,
                "explanation": explanation,
                "evaluator": evaluator,
            },
            prefer="return=minimal",
        )

    def list_evaluations(self, application_id: str) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "evaluations",
            query={"application_id": f"eq.{application_id}", "order": "evaluated_at.asc,id.asc"},
        )

    def insert_work_item(
        self,
        work_item_id: str,
        application_id: str,
        kind: str,
        idempotency_key: str,
        reason: str,
    ) -> None:
        existing = self._request(
            "GET",
            "work_items",
            query={"idempotency_key": f"eq.{idempotency_key}", "limit": "1"},
        )
        if existing:
            return
        self._request(
            "POST",
            "work_items",
            payload={
                "id": work_item_id,
                "application_id": application_id,
                "kind": kind,
                "idempotency_key": idempotency_key,
                "reason": reason,
            },
            prefer="return=minimal",
        )

    def list_work_items(self, application_id: str) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "work_items",
            query={
                "application_id": f"eq.{application_id}",
                "order": "created_at.asc,id.asc",
            },
        )

    def insert_audit_event(
        self,
        event_id: str,
        actor_type: str,
        actor_id: str | None,
        action: str,
        entity_type: str,
        entity_id: str,
        before_state: Any,
        after_state: Any,
        reason: str | None,
        correlation_id: str,
        source_version: str,
    ) -> None:
        self._request(
            "POST",
            "audit_events",
            payload={
                "id": event_id,
                "actor_type": actor_type,
                "actor_id": actor_id,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "before": before_state,
                "after": after_state,
                "reason": reason,
                "correlation_id": correlation_id,
                "source_version": source_version,
            },
            prefer="return=minimal",
        )

    def list_audit_events(self, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "audit_events",
            query={
                "entity_type": f"eq.{entity_type}",
                "entity_id": f"eq.{entity_id}",
                "order": "occurred_at.asc,id.asc",
            },
        )
