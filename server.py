# server.py
import uvicorn
import sys
import os
from orket.runtime import create_api_app
from orket.utils import get_reload_excludes

app = create_api_app()

if __name__ == "__main__":
    try:
        uvicorn.run(
            "server:app", 
            host=os.getenv("ORKET_HOST", "0.0.0.0"), 
            port=int(os.getenv("ORKET_PORT", "8082")), 
            reload=True, 
            reload_excludes=get_reload_excludes()
        )
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Orket Server failed to start: {e}")
        import traceback
        from orket.logging import log_crash
        log_crash(e, traceback.format_exc())
        traceback.print_exc()
        sys.exit(1)
