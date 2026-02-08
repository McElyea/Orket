# server.py
import uvicorn
from orket.interfaces.api import app

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8082, reload=True, reload_excludes=["workspace/*", "product/*"])
