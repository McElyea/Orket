import asyncio
import sys
import traceback
from pathlib import Path

import uvicorn

import orket.settings as settings_module
from orket.application.services.crash_report_service import CrashReportService
from orket.interfaces.api_reload_runtime import run_reloading_api_server
from orket.interfaces.runtime_entrypoints import create_api_app
from orket.interfaces.server_launcher import (
    LauncherConfigError,
    build_api_server_arg_parser,
    resolve_api_launch_settings_from_namespace,
)
from orket.runtime import CompositionConfig
from orket.utils import get_reload_excludes

PROJECT_ROOT = Path(__file__).resolve().parent


def _bootstrap_server_environment() -> None:
    settings_module.ENV_FILE = PROJECT_ROOT / ".env"
    settings_module.load_env()
    # Spawned reload workers execute this module before uvicorn starts their loop.
    # Bind both snapshots for the later server:app import inside that loop.
    settings_module.set_runtime_settings_context(
        user_settings=settings_module.load_user_settings(),
        user_preferences=settings_module.load_user_preferences(),
    )


_bootstrap_server_environment()
app = create_api_app(CompositionConfig(project_root=PROJECT_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = build_api_server_arg_parser()
    args = parser.parse_args(argv)
    try:
        settings = resolve_api_launch_settings_from_namespace(args)
        run_kwargs = {
            "host": settings.host,
            "port": settings.port,
        }
        if settings.reload:
            run_reloading_api_server("server:app", **run_kwargs, reload_excludes=get_reload_excludes())
        else:
            # Avoid a second module import during uvicorn startup; importing via
            # string in non-reload mode can happen after loop start.
            uvicorn.run(app, **run_kwargs)
        return 0
    except LauncherConfigError as exc:
        print(f"[CONFIG ERROR] {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"\n[CRITICAL ERROR] Orket Server failed to start: {exc}")
        detail = traceback.format_exc()
        traceback.print_exc()
        try:
            path = asyncio.run(CrashReportService(PROJECT_ROOT / "workspace/default").publish(exc, detail))
            print(f"Crash report saved: {path}", file=sys.stderr)
        except Exception as publication_error:
            # The synchronous launcher boundary must preserve its original failure.
            print(f"Crash report publication failed: {publication_error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
