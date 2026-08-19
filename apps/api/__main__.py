"""Run the seeded local demo API with ``python -m apps.api``."""

from __future__ import annotations

import argparse
from pathlib import Path

from .server import create_demo_server


def prepare_demo_database(db_path: str | Path, *, reset: bool = False) -> Path:
    """Resolve the demo database and, when requested, remove only its local fixture files."""

    selected = Path(db_path).resolve()
    if not reset:
        return selected

    fixture_root = (Path.cwd() / ".local").resolve()
    if selected.suffix != ".sqlite3" or selected.parent != fixture_root:
        raise ValueError(
            "Reset is limited to an explicit .local/*.sqlite3 fixture SQLite database"
        )
    for path in (selected, Path(f"{selected}-wal"), Path(f"{selected}-shm")):
        path.unlink(missing_ok=True)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the recruiting demo API")
    parser.add_argument("--db", default=None)
    parser.add_argument("--port", type=int, default=8104)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Recreate the explicitly selected .local SQLite fixture before launch",
    )
    args = parser.parse_args()

    if args.reset and args.db is None:
        parser.error("--reset requires an explicit --db .local/*.sqlite3 path")
    db_path = prepare_demo_database(args.db or ".local/demo.sqlite3", reset=args.reset)
    server = create_demo_server(db_path, port=args.port)
    print(f"Recruiting demo API listening on http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        server.demo_store.close()  # type: ignore[attr-defined]


if __name__ == "__main__":
    main()
