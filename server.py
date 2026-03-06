import sys
import traceback

import uvicorn

from orket.interfaces.server_launcher import LauncherConfigError
from orket.interfaces.server_launcher import build_api_server_arg_parser
from orket.interfaces.server_launcher import resolve_api_launch_settings_from_namespace
from orket.runtime import create_api_app
from orket.utils import get_reload_excludes

app = create_api_app()


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
            run_kwargs["reload"] = True
            run_kwargs["reload_excludes"] = get_reload_excludes()

        uvicorn.run("server:app", **run_kwargs)
        return 0
    except LauncherConfigError as exc:
        print(f"[CONFIG ERROR] {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"\n[CRITICAL ERROR] Orket Server failed to start: {exc}")
        from orket.logging import log_crash

        log_crash(exc, traceback.format_exc())
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
