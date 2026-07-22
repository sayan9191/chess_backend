"""CLI entry point: chess-backend serve | migrate | version"""

from __future__ import annotations

import argparse
import os
import sys


def _cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    host = args.host or os.environ.get("HOST", "0.0.0.0")
    port = args.port or int(os.environ.get("PORT", "8000"))
    reload = args.reload and os.environ.get("ENVIRONMENT", "development") == "development"

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )


def _find_project_root() -> str:
    """Locate directory containing alembic.ini (repo root or install root)."""
    candidates = [
        os.getcwd(),
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ]
    for root in candidates:
        if os.path.isfile(os.path.join(root, "alembic.ini")):
            return root
    raise FileNotFoundError(
        "alembic.ini not found. Run from the backend/ directory or install with [migrate] extra."
    )


def _cmd_migrate(args: argparse.Namespace) -> None:
    try:
        from alembic import command
        from alembic.config import Config
    except ImportError as exc:
        print(
            "Alembic not installed. Run: pip install 'chess-backend[migrate]'",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    root = _find_project_root()
    ini_path = os.path.join(root, "alembic.ini")
    cfg = Config(ini_path)
    command.upgrade(cfg, args.revision)


def _cmd_version(_: argparse.Namespace) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    print(f"chess-backend {settings.app_version}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="chess-backend",
        description="Chess Backend API — serve, migrate, or print version",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    serve_p = sub.add_parser("serve", help="Start the API server")
    serve_p.add_argument("--host", default=None, help="Bind host (default: 0.0.0.0)")
    serve_p.add_argument("--port", type=int, default=None, help="Bind port (default: PORT env or 8000)")
    serve_p.add_argument("--reload", action="store_true", help="Auto-reload on code changes")
    serve_p.set_defaults(func=_cmd_serve)

    migrate_p = sub.add_parser("migrate", help="Run Alembic migrations")
    migrate_p.add_argument("--revision", default="head", help="Target revision (default: head)")
    migrate_p.set_defaults(func=_cmd_migrate)

    version_p = sub.add_parser("version", help="Print package version")
    version_p.set_defaults(func=_cmd_version)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
