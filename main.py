# main.py
import asyncio
import sys
from orket.runtime import create_cli_runtime

if __name__ == "__main__":
    try:
        run_cli = create_cli_runtime()
        asyncio.run(run_cli())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Orket CLI crashed: {e}")
        # Optional: Log full traceback to file but show summary to user
        import traceback
        from orket.logging import log_crash
        log_crash(e, traceback.format_exc())
        print("A detailed crash log has been saved to 'orket_crash.log'.")
        sys.exit(1)
