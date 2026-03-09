from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="Companion Template")


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Companion Template</title>
    <style>
      body { font-family: system-ui, sans-serif; margin: 2rem; }
      .card { max-width: 52rem; padding: 1rem 1.25rem; border: 1px solid #ddd; border-radius: 10px; }
      code { background: #f5f5f5; padding: 0.1rem 0.3rem; border-radius: 4px; }
    </style>
  </head>
  <body>
    <div class="card">
      <h1>Companion Template</h1>
      <p>This starter app is intentionally minimal.</p>
      <p>Host API authority lives at <code>/api/v1/companion</code> on the Orket host.</p>
    </div>
  </body>
</html>
"""
