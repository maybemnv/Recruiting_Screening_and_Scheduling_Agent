"""Small SQLite persistence boundary for the local demo slice."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class SQLiteStore:
    """Own the local database connection and the requirement tables."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                slug TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS requirement_versions (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL REFERENCES jobs(id),
                version INTEGER NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('draft', 'published', 'retired')),
                published_at TEXT,
                UNIQUE(job_id, version)
            );

            CREATE TABLE IF NOT EXISTS criteria (
                version_id TEXT PRIMARY KEY REFERENCES requirement_versions(id),
                payload TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS applications (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL REFERENCES jobs(id),
                requirement_version_id TEXT NOT NULL REFERENCES requirement_versions(id),
                external_application_id TEXT,
                contact TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'received',
                consent TEXT NOT NULL,
                resume_status TEXT NOT NULL DEFAULT 'not_provided',
                resume_file_id TEXT,
                disposition TEXT,
                disposition_reason TEXT,
                dispositioned_by TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY,
                application_id TEXT NOT NULL REFERENCES applications(id),
                criterion_id TEXT,
                source TEXT NOT NULL,
                value TEXT,
                source_reference TEXT NOT NULL,
                confidence REAL,
                extraction_status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS evaluations (
                id TEXT PRIMARY KEY,
                application_id TEXT NOT NULL REFERENCES applications(id),
                requirement_version_id TEXT NOT NULL REFERENCES requirement_versions(id),
                criterion_id TEXT NOT NULL,
                result TEXT NOT NULL,
                evidence_ids TEXT NOT NULL,
                rule_expression TEXT NOT NULL,
                explanation TEXT NOT NULL,
                evaluator TEXT NOT NULL,
                evaluated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(application_id, requirement_version_id, criterion_id)
            );

            CREATE TABLE IF NOT EXISTS work_items (
                id TEXT PRIMARY KEY,
                application_id TEXT REFERENCES applications(id),
                kind TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'queued',
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error_code TEXT,
                next_attempt_at TEXT,
                reason TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY,
                occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                actor_type TEXT NOT NULL,
                actor_id TEXT,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                before_state TEXT,
                after_state TEXT,
                reason TEXT,
                correlation_id TEXT NOT NULL,
                source_version TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def close(self) -> None:
        with self._lock:
            self.connection.close()

    def insert_job(self, job_id: str, slug: str, title: str) -> None:
        with self._lock:
            self.connection.execute(
                "INSERT INTO jobs (id, slug, title) VALUES (?, ?, ?)",
                (job_id, slug, title),
            )
            self.connection.commit()

    def get_job(self, job_id: str) -> sqlite3.Row | None:
        with self._lock:
            return self.connection.execute(
                "SELECT id, slug, title FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()

    def get_job_by_slug(self, slug: str) -> sqlite3.Row | None:
        with self._lock:
            return self.connection.execute(
                "SELECT id, slug, title FROM jobs WHERE slug = ?", (slug,)
            ).fetchone()

    def list_jobs(self) -> list[sqlite3.Row]:
        with self._lock:
            return list(
                self.connection.execute(
                    "SELECT id, slug, title FROM jobs ORDER BY title"
                ).fetchall()
            )

    def next_version_number(self, job_id: str) -> int:
        with self._lock:
            row = self.connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 AS next_version "
                "FROM requirement_versions WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        return int(row["next_version"])

    def insert_requirement_version(
        self,
        version_id: str,
        job_id: str,
        version: int,
        payload: list[dict[str, Any]],
    ) -> None:
        with self._lock:
            self.connection.execute(
                "INSERT INTO requirement_versions (id, job_id, version, status) "
                "VALUES (?, ?, ?, 'draft')",
                (version_id, job_id, version),
            )
            self.connection.execute(
                "INSERT INTO criteria (version_id, payload) VALUES (?, ?)",
                (version_id, json.dumps(payload, sort_keys=True)),
            )
            self.connection.commit()

    def update_criteria(self, version_id: str, payload: list[dict[str, Any]]) -> None:
        with self._lock:
            self.connection.execute(
                "UPDATE criteria SET payload = ? WHERE version_id = ?",
                (json.dumps(payload, sort_keys=True), version_id),
            )
            self.connection.commit()

    def get_requirement_version(self, version_id: str) -> sqlite3.Row | None:
        with self._lock:
            return self.connection.execute(
                "SELECT id, job_id, version, status, published_at "
                "FROM requirement_versions WHERE id = ?",
                (version_id,),
            ).fetchone()

    def get_criteria(self, version_id: str) -> list[dict[str, Any]]:
        with self._lock:
            row = self.connection.execute(
                "SELECT payload FROM criteria WHERE version_id = ?", (version_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown requirement version: {version_id}")
        return json.loads(row["payload"])

    def publish_requirement_version(self, version_id: str) -> None:
        with self._lock:
            self.connection.execute(
                "UPDATE requirement_versions SET status = 'published', "
                "published_at = CURRENT_TIMESTAMP WHERE id = ?",
                (version_id,),
            )
            self.connection.commit()

    def get_latest_published(self, job_id: str) -> sqlite3.Row | None:
        with self._lock:
            return self.connection.execute(
                "SELECT id, job_id, version, status, published_at "
                "FROM requirement_versions "
                "WHERE job_id = ? AND status = 'published' "
                "ORDER BY version DESC LIMIT 1",
                (job_id,),
            ).fetchone()


    def list_requirement_versions(self, job_id: str) -> list[sqlite3.Row]:
        with self._lock:
            return list(
                self.connection.execute(
                    "SELECT id, job_id, version, status, published_at "
                    "FROM requirement_versions WHERE job_id = ? "
                    "ORDER BY version DESC",
                    (job_id,),
                ).fetchall()
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
        with self._lock:
            self.connection.execute(
                "INSERT INTO applications "
                "(id, job_id, requirement_version_id, contact, status, consent, "
                "resume_status, resume_file_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    application_id,
                    job_id,
                    requirement_version_id,
                    json.dumps(contact, sort_keys=True),
                    status,
                    json.dumps(consent, sort_keys=True),
                    resume_status,
                    resume_file_id,
                ),
            )
            self.connection.commit()

    def get_application(self, application_id: str) -> sqlite3.Row | None:
        with self._lock:
            return self.connection.execute(
                "SELECT * FROM applications WHERE id = ?", (application_id,)
            ).fetchone()

    def list_applications(self, job_id: str) -> list[sqlite3.Row]:
        with self._lock:
            return list(
                self.connection.execute(
                    "SELECT * FROM applications WHERE job_id = ? ORDER BY created_at, id",
                    (job_id,),
                ).fetchall()
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
        assignments = ["updated_at = CURRENT_TIMESTAMP"]
        values: list[Any] = []
        for column, value in (
            ("status", status),
            ("disposition", disposition),
            ("disposition_reason", disposition_reason),
            ("dispositioned_by", dispositioned_by),
        ):
            if value is not None:
                assignments.append(f"{column} = ?")
                values.append(value)
        values.append(application_id)
        with self._lock:
            self.connection.execute(
                f"UPDATE applications SET {', '.join(assignments)} WHERE id = ?",
                values,
            )
            self.connection.commit()

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
        with self._lock:
            self.connection.execute(
                "INSERT INTO evidence "
                "(id, application_id, criterion_id, source, value, source_reference, "
                "confidence, extraction_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    evidence_id,
                    application_id,
                    criterion_id,
                    source,
                    json.dumps(value, sort_keys=True),
                    json.dumps(source_reference, sort_keys=True),
                    confidence,
                    extraction_status,
                ),
            )
            self.connection.commit()

    def list_evidence(self, application_id: str) -> list[sqlite3.Row]:
        with self._lock:
            return list(
                self.connection.execute(
                    "SELECT * FROM evidence WHERE application_id = ? ORDER BY created_at, id",
                    (application_id,),
                ).fetchall()
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
        with self._lock:
            self.connection.execute(
                "INSERT INTO evaluations "
                "(id, application_id, requirement_version_id, criterion_id, result, "
                "evidence_ids, rule_expression, explanation, evaluator) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    evaluation_id,
                    application_id,
                    requirement_version_id,
                    criterion_id,
                    result,
                    json.dumps(evidence_ids, sort_keys=True),
                    rule_expression,
                    explanation,
                    evaluator,
                ),
            )
            self.connection.commit()

    def list_evaluations(self, application_id: str) -> list[sqlite3.Row]:
        with self._lock:
            return list(
                self.connection.execute(
                    "SELECT * FROM evaluations WHERE application_id = ? ORDER BY rowid",
                    (application_id,),
                ).fetchall()
            )

    def insert_work_item(
        self,
        work_item_id: str,
        application_id: str,
        kind: str,
        idempotency_key: str,
        reason: str,
    ) -> None:
        with self._lock:
            self.connection.execute(
                "INSERT OR IGNORE INTO work_items "
                "(id, application_id, kind, idempotency_key, reason) VALUES (?, ?, ?, ?, ?)",
                (work_item_id, application_id, kind, idempotency_key, reason),
            )
            self.connection.commit()

    def list_work_items(self, application_id: str) -> list[sqlite3.Row]:
        with self._lock:
            return list(
                self.connection.execute(
                    "SELECT * FROM work_items WHERE application_id = ? ORDER BY created_at, id",
                    (application_id,),
                ).fetchall()
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
        with self._lock:
            self.connection.execute(
                "INSERT INTO audit_events "
                "(id, actor_type, actor_id, action, entity_type, entity_id, before_state, "
                "after_state, reason, correlation_id, source_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    actor_type,
                    actor_id,
                    action,
                    entity_type,
                    entity_id,
                    json.dumps(before_state, sort_keys=True),
                    json.dumps(after_state, sort_keys=True),
                    reason,
                    correlation_id,
                    source_version,
                ),
            )
            self.connection.commit()

    def list_audit_events(self, entity_type: str, entity_id: str) -> list[sqlite3.Row]:
        with self._lock:
            return list(
                self.connection.execute(
                    "SELECT * FROM audit_events WHERE entity_type = ? AND entity_id = "
                    "? ORDER BY occurred_at, id",
                    (entity_type, entity_id),
                ).fetchall()
            )
