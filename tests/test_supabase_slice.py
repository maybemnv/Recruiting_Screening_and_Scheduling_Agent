import json
from datetime import datetime
from pathlib import Path

from apps.api.config import BackendConfig
from apps.api.storage import SQLiteStore
from apps.api.store_factory import create_store
from apps.api.supabase_store import SupabaseStore
import apps.api.supabase_store as supabase_store_module


class _EmptyResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return b""


def test_store_factory_selects_sqlite_without_external_dependencies(tmp_path):
    config = BackendConfig(
        backend="sqlite", sqlite_path=str(tmp_path / "factory.sqlite3")
    )

    store = create_store(config)
    try:
        assert isinstance(store, SQLiteStore)
        assert store.path.endswith("factory.sqlite3")
    finally:
        store.close()


def test_store_factory_selects_server_side_supabase_store():
    config = BackendConfig(
        backend="supabase",
        supabase_url="https://demo.supabase.co",
        supabase_service_role_key="server-only",
    )

    store = create_store(config)

    assert isinstance(store, SupabaseStore)
    assert store.rest_url == "https://demo.supabase.co/rest/v1"
    store.close()


def test_supabase_publish_sends_a_parseable_timestamp_and_server_only_headers(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return _EmptyResponse()

    monkeypatch.setattr(supabase_store_module, "urlopen", fake_urlopen)
    store = SupabaseStore("https://demo.supabase.co/rest/v1", "server-only")

    store.publish_requirement_version("retail-job-v2")

    request = captured["request"]
    payload = json.loads(request.data.decode("utf-8"))
    assert payload["status"] == "published"
    assert payload["published_at"] != "now()"
    datetime.fromisoformat(payload["published_at"])
    assert request.get_header("Apikey") == "server-only"
    assert request.get_header("Authorization") == "Bearer server-only"
    assert captured["timeout"] == 15


def test_supabase_migration_defines_requirement_tables_and_fail_closed_rls():
    migration = Path("supabase/migrations/001_recruiting_demo.sql").read_text(
        encoding="utf-8"
    )

    for table in (
        "jobs",
        "requirement_versions",
        "criteria",
        "applications",
        "evidence",
        "evaluations",
        "work_items",
        "audit_events",
    ):
        assert f"create table if not exists public.{table}" in migration.lower()
        assert f"alter table public.{table} enable row level security" in migration.lower()

    assert "no anon/authenticated policies" in migration.lower()
