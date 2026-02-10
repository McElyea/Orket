# server.py
import uvicorn
from orket.interfaces.api import app

RELOAD_EXCLUDES = ["workspace/*", "product/*", "logs/*", "*.db"]

if __name__ == "__main__":
    try:
        uvicorn.run(
            "server:app", 
            host="127.0.0.1", 
            port=8082, 
            reload=True, 
            reload_excludes=RELOAD_EXCLUDES
        )
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Orket Server failed to start: {e}")
        import traceback
        traceback.print_exc()

