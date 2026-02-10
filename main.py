# main.py
import asyncio
from orket.interfaces.cli import run_cli

if __name__ == "__main__":
    try:
        asyncio.run(run_cli())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Orket CLI crashed: {e}")
        # Optional: Log full traceback to file but show summary to user
        import traceback
        with open("orket_crash.log", "a") as f:
            f.write(f"\n--- {type(e).__name__} at {__import__('datetime').datetime.now()} ---\n")
            f.write(traceback.format_exc())
        print("A detailed crash log has been saved to 'orket_crash.log'.")

