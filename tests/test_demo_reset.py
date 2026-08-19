from pathlib import Path

import pytest

from apps.api import __main__ as demo_main
from apps.api.server import create_demo_server


def test_reset_recreates_only_selected_local_fixture_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    selected = Path(".local/demo.sqlite3")
    selected.parent.mkdir()
    selected.write_bytes(b"stale fixture database")
    untouched = selected.parent / "keep.sqlite3"
    untouched.write_bytes(b"do not remove")

    assert callable(getattr(demo_main, "prepare_demo_database", None))
    resolved = demo_main.prepare_demo_database(selected, reset=True)
    assert resolved == selected.resolve()
    assert not selected.exists()
    assert untouched.read_bytes() == b"do not remove"

    server = create_demo_server(resolved)
    try:
        jobs = server.demo_store.list_jobs()
        assert [job["id"] for job in jobs] == ["retail-job"]
    finally:
        server.server_close()
        server.demo_store.close()

    demo_main.prepare_demo_database(selected, reset=True)
    assert not selected.exists()
    assert untouched.read_bytes() == b"do not remove"


@pytest.mark.parametrize(
    "unsafe_path",
    [Path("other/demo.sqlite3"), Path(".local/demo.db"), Path("../demo.sqlite3")],
)
def test_reset_rejects_paths_outside_local_sqlite_fixture_boundary(
    tmp_path, monkeypatch, unsafe_path
):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="fixture SQLite"):
        demo_main.prepare_demo_database(unsafe_path, reset=True)
