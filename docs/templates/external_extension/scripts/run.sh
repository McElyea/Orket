#!/usr/bin/env bash
set -euo pipefail

python -m uvicorn companion_app.server:app --app-dir src --host 127.0.0.1 --port 3000
