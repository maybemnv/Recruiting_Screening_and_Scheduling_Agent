"""Runtime configuration for the fixture and Supabase persistence modes."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


class ConfigurationError(ValueError):
    """Raised when the selected runtime backend is not configured safely."""


@dataclass(frozen=True, repr=False)
class BackendConfig:
    """Server-side storage settings; secrets are intentionally excluded from repr."""

    app_env: str = "production"
    backend: str = "sqlite"
    sqlite_path: str = ".local/demo.sqlite3"
    supabase_url: str | None = None
    supabase_service_role_key: str | None = field(default=None, repr=False)
    calendar_mode: str = "fixture"
    messaging_mode: str = "fixture"

    @classmethod
    def from_environment(cls) -> "BackendConfig":
        app_env = os.getenv("APP_ENV", "production").strip().lower()
        if app_env not in {"local-fixture", "staging", "production"}:
            raise ConfigurationError(
                "APP_ENV must be local-fixture, staging, or production"
            )
        backend = os.getenv("RECRUITING_STORE_BACKEND", "sqlite").strip().lower()
        if backend not in {"sqlite", "supabase"}:
            raise ConfigurationError(
                "RECRUITING_STORE_BACKEND must be 'sqlite' or 'supabase'"
            )

        url = os.getenv("SUPABASE_URL", "").strip().rstrip("/") or None
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or None
        if backend == "supabase":
            missing = [
                name
                for name, value in (
                    ("SUPABASE_URL", url),
                    ("SUPABASE_SERVICE_ROLE_KEY", service_key),
                )
                if not value
            ]
            if missing:
                raise ConfigurationError(
                    "Supabase backend requires: " + ", ".join(missing)
                )

        calendar_mode = os.getenv("RECRUITING_DEMO_CALENDAR_MODE", "fixture").strip().lower()
        messaging_mode = os.getenv("RECRUITING_DEMO_MESSAGING_MODE", "fixture").strip().lower()
        if calendar_mode not in {"fixture", "outage"}:
            raise ConfigurationError("RECRUITING_DEMO_CALENDAR_MODE must be 'fixture' or 'outage'")
        if messaging_mode not in {"fixture", "outage"}:
            raise ConfigurationError("RECRUITING_DEMO_MESSAGING_MODE must be 'fixture' or 'outage'")
        if app_env != "local-fixture":
            if backend == "sqlite":
                raise ConfigurationError("SQLite fixture backend requires APP_ENV=local-fixture")
            if calendar_mode in {"fixture", "outage"} or messaging_mode in {"fixture", "outage"}:
                raise ConfigurationError("fixture provider modes require APP_ENV=local-fixture")

        return cls(
            app_env=app_env,
            backend=backend,
            sqlite_path=os.getenv("RECRUITING_SQLITE_PATH", ".local/demo.sqlite3"),
            supabase_url=url,
            supabase_service_role_key=service_key,
            calendar_mode=calendar_mode,
            messaging_mode=messaging_mode,
        )

    @property
    def rest_url(self) -> str | None:
        if self.supabase_url is None:
            return None
        return f"{self.supabase_url}/rest/v1"

    def __repr__(self) -> str:
        return (
            "BackendConfig("
            f"app_env={self.app_env!r}, "
            f"backend={self.backend!r}, "
            f"sqlite_path={self.sqlite_path!r}, "
            f"supabase_url={self.supabase_url!r}, "
            f"calendar_mode={self.calendar_mode!r}, "
            f"messaging_mode={self.messaging_mode!r}, "
            "supabase_service_role_key='[REDACTED]')"
        )
