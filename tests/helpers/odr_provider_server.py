"""Local HTTP protocol fixture; it never represents actual model inference."""
from __future__ import annotations

import json
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

MODEL = "odr-fixture-model"
ARCHITECT = """### REQUIREMENT
The application stores profile data locally. Retention duration is DECISION_REQUIRED.
### CHANGELOG
- Preserved local storage.
### ASSUMPTIONS
- None.
### OPEN_QUESTIONS
- Retention duration is DECISION_REQUIRED.
"""
AUDITOR = """### CRITIQUE
- Retention duration needs a decision.
### PATCHES
- Preserve DECISION_REQUIRED for retention duration.
### EDGE_CASES
- Missing retention duration.
### TEST_GAPS
- Resolve the retention decision before acceptance.
"""


@contextmanager
def provider_server(*, mode="success"):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def reply(self, payload, status=200):
            raw = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            calls.append(("GET", self.path))
            if mode == "unavailable":
                self.reply({"error": "fixture unavailable"}, 503)
            else:
                self.reply({"data": [{"id": MODEL}]} if mode != "missing" else {"data": []})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(("POST", self.path, body))
            if mode == "inference-failure":
                self.reply({"error": "fixture inference failure"}, 400)
                return
            system = body["messages"][0]["content"]
            content = ARCHITECT if "Architect role" in system else AUDITOR
            self.reply({"id": "odr-protocol-fixture", "model": MODEL,
                "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10}})

        def log_message(self, *args):
            # HTTP fixture calls are retained explicitly above; default stderr is redundant.
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()
