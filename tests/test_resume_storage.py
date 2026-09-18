import pytest

from apps.api.resume_storage import ResumeStorage


def test_fixture_resume_storage_uses_private_local_files(tmp_path):
    storage = ResumeStorage("local", str(tmp_path))
    uri = storage.put(b"candidate resume", application_id="application-1")
    assert uri.startswith("file:")
    storage.delete(uri)


def test_s3_resume_storage_requires_a_bucket(monkeypatch):
    monkeypatch.delenv("RECRUITING_RESUME_BUCKET", raising=False)
    with pytest.raises(ValueError, match="RECRUITING_RESUME_BUCKET"):
        ResumeStorage("s3")
