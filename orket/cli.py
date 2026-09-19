from __future__ import annotations

import asyncio
import sys
import traceback
from pathlib import Path


def _run_runtime_command(argv: list[str]) -> int:
    invocation_root = None
    try:
        invocation_root = Path.cwd()
        from orket.interfaces.runtime_entrypoints import create_cli_runtime
        from orket.settings import load_env

        load_env()
        run_cli = create_cli_runtime()
        return int(asyncio.run(run_cli(argv, prog="orket runtime")))
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 130
    except Exception as exc:
        print(f"\n[CRITICAL ERROR] Orket CLI crashed: {exc}")
        return _report_runtime_crash(invocation_root, exc, traceback.format_exc())


def _report_runtime_crash(invocation_root: Path | None, exception: Exception, traceback_text: str) -> int:
    try:
        from orket.application.services.crash_report_service import CrashReportService

        if invocation_root is None:
            raise ValueError("Invocation directory unavailable")
        service = CrashReportService(invocation_root / "workspace/default")
        path = asyncio.run(service.publish(exception, traceback_text))
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 130
    except Exception as diagnostic_error:
        # This is the CLI's final diagnostic boundary; preserve both failures.
        print(traceback_text, file=sys.stderr)
        print(f"Crash report publication failed: {type(diagnostic_error).__name__}: {diagnostic_error}", file=sys.stderr)
        return 1
    print(f"A detailed crash log has been saved to '{path}'.")
    return 1


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ["runtime"]:
        return _run_runtime_command(arguments[1:])

    from orket.interfaces.orket_bundle_cli import main as bundle_main

    return int(bundle_main(arguments))


if __name__ == "__main__":
    raise SystemExit(main())
