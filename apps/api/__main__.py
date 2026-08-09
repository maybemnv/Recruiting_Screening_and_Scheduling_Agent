"""Run the seeded local demo API with ``python -m apps.api``."""

from __future__ import annotations

import argparse

from .server import create_demo_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the recruiting demo API")
    parser.add_argument("--db", default=".local/demo.sqlite3")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = create_demo_server(args.db, port=args.port)
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
