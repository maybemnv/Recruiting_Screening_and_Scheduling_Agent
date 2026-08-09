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
