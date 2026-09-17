from __future__ import annotations

import asyncio
import sys
import traceback


def _run_runtime_command(argv: list[str]) -> int:
    from orket.logging import log_crash
    from orket.runtime import create_cli_runtime
    from orket.settings import load_env

    try:
        load_env()
        run_cli = create_cli_runtime()
        return int(asyncio.run(run_cli(argv, prog="orket runtime")))
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 130
    except Exception as exc:
        print(f"\n[CRITICAL ERROR] Orket CLI crashed: {exc}")
        log_crash(exc, traceback.format_exc())
        print("A detailed crash log has been saved to 'orket_crash.log'.")
        return 1


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ["runtime"]:
        return _run_runtime_command(arguments[1:])

    from orket.interfaces.orket_bundle_cli import main as bundle_main

    return int(bundle_main(arguments))


if __name__ == "__main__":
    raise SystemExit(main())
