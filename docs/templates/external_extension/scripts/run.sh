#!/usr/bin/env bash
set -euo pipefail

ui_host="${COMPANION_UI_HOST:-127.0.0.1}"
start_port="${COMPANION_UI_PORT:-3000}"
max_port="${COMPANION_UI_MAX_PORT:-$((start_port + 20))}"

if [ "${max_port}" -lt "${start_port}" ]; then
  echo "COMPANION_UI_MAX_PORT (${max_port}) must be >= COMPANION_UI_PORT (${start_port})." >&2
  exit 2
fi

ui_port="$(
python - <<'PY' "${ui_host}" "${start_port}" "${max_port}"
import socket
import sys

host = sys.argv[1]
start_port = int(sys.argv[2])
max_port = int(sys.argv[3])

for port in range(start_port, max_port + 1):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
    except OSError:
        pass
    else:
        print(port)
        sock.close()
        raise SystemExit(0)
    finally:
        try:
            sock.close()
        except OSError:
            pass

raise SystemExit(1)
PY
)"

if [ -z "${ui_port}" ]; then
  echo "No open UI port found in range ${start_port}-${max_port} on ${ui_host}." >&2
  exit 1
fi

if [ "${ui_port}" != "${start_port}" ]; then
  echo "Port ${start_port} is in use; using ${ui_port} instead."
fi

python -m uvicorn companion_app.server:app --app-dir src --host "${ui_host}" --port "${ui_port}"
