"""Runtime configuration for the fixture and Supabase persistence modes."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


class ConfigurationError(ValueError):
    """Raised when the selected runtime backend is not configured safely."""


@dataclass(frozen=True, repr=False)
class BackendConfig:
    """Server-side storage settings; secrets are intentionally excluded from repr."""

    backend: str = "sqlite"
    sqlite_path: str = ".local/demo.sqlite3"
    supabase_url: str | None = None
    supabase_service_role_key: str | None = field(default=None, repr=False)

    @classmethod
    def from_environment(cls) -> "BackendConfig":
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

        return cls(
            backend=backend,
            sqlite_path=os.getenv("RECRUITING_SQLITE_PATH", ".local/demo.sqlite3"),
            supabase_url=url,
            supabase_service_role_key=service_key,
        )

    @property
    def rest_url(self) -> str | None:
        if self.supabase_url is None:
            return None
        return f"{self.supabase_url}/rest/v1"

    def __repr__(self) -> str:
        return (
            "BackendConfig("
            f"backend={self.backend!r}, "
            f"sqlite_path={self.sqlite_path!r}, "
            f"supabase_url={self.supabase_url!r}, "
            "supabase_service_role_key='[REDACTED]')"
        )
