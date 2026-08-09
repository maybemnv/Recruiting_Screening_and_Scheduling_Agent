"""Select the configured persistence boundary without leaking credentials."""

from __future__ import annotations

from pathlib import Path

from .config import BackendConfig, ConfigurationError
from .storage import SQLiteStore
from .supabase_store import SupabaseStore


def create_store(
    config: BackendConfig, sqlite_path: str | Path | None = None
) -> SQLiteStore | SupabaseStore:
    if config.backend == "sqlite":
        return SQLiteStore(sqlite_path or config.sqlite_path)
    if config.backend == "supabase":
        if not config.rest_url or not config.supabase_service_role_key:
            raise ConfigurationError("Supabase backend is missing server credentials")
        return SupabaseStore(config.rest_url, config.supabase_service_role_key)
    raise ConfigurationError(f"Unsupported storage backend: {config.backend}")
