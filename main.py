# main.py
import asyncio
import sys
import traceback

from orket.logging import log_crash
from orket.runtime import create_cli_runtime
from orket.settings import load_env

if __name__ == "__main__":
    try:
        load_env()
        run_cli = create_cli_runtime()
        asyncio.run(run_cli())
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"\n[CRITICAL ERROR] Orket CLI crashed: {exc}")
        log_crash(exc, traceback.format_exc())
        print("A detailed crash log has been saved to 'orket_crash.log'.")
        sys.exit(1)
