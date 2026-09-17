import pytest

from apps.api.config import BackendConfig, ConfigurationError


def test_fixture_backend_is_default_without_credentials(monkeypatch):
    monkeypatch.delenv("RECRUITING_STORE_BACKEND", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    config = BackendConfig.from_environment()

    assert config.backend == "sqlite"
    assert config.sqlite_path == ".local/demo.sqlite3"
    assert config.supabase_url is None


def test_supabase_backend_requires_server_only_credentials(monkeypatch):
    monkeypatch.setenv("RECRUITING_STORE_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://demo.supabase.co/")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    with pytest.raises(ConfigurationError, match="SUPABASE_SERVICE_ROLE_KEY"):
        BackendConfig.from_environment()


def test_supabase_backend_normalizes_url_and_never_exposes_key(monkeypatch):
    monkeypatch.setenv("RECRUITING_STORE_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://demo.supabase.co/")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "server-secret")

    config = BackendConfig.from_environment()

    assert config.backend == "supabase"
    assert config.supabase_url == "https://demo.supabase.co"
    assert config.rest_url == "https://demo.supabase.co/rest/v1"
    assert config.supabase_service_role_key == "server-secret"
    assert "server-secret" not in repr(config)


def test_fixture_backend_is_rejected_outside_local_fixture(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("RECRUITING_STORE_BACKEND", "sqlite")

    with pytest.raises(ConfigurationError, match="local-fixture"):
        BackendConfig.from_environment()


def test_production_requires_server_side_auth_token(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RECRUITING_STORE_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://demo.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "server-secret")
    monkeypatch.setenv("RECRUITING_RESUME_STORAGE", "s3")
    monkeypatch.delenv("RECRUITING_AUTH_BEARER_TOKEN", raising=False)

    with pytest.raises(ConfigurationError, match="RECRUITING_AUTH_BEARER_TOKEN"):
        BackendConfig.from_environment()
