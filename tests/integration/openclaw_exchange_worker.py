"""Standalone real pipe fixture for sequential JSONL admission and bounded failures."""
import json
import os
import queue
import sys
import threading
import time
from pathlib import Path


def _read_requests(root, requests):
    for index, line in enumerate(sys.stdin.buffer):
        request = json.loads(line)
        (root / f"request-{index}.json").write_text(json.dumps(request), encoding="utf-8")
        requests.put(request)
    requests.put(None)


def _respond(root, mode, index, request):
    if mode == "sequence" and index == 0:
        (root / "first-read").touch()
        deadline = time.monotonic() + 10
        while not (root / "release-response").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
    if mode.startswith("stderr"):
        sys.stderr.buffer.write(b"e" * (5 * 1024 * 1024 if mode == "stderr-limit" else 512 * 1024))
        sys.stderr.buffer.flush()
    if mode == "line-limit":
        print(json.dumps({"payload": "x" * 70000}), flush=True)
    elif index == 1 and mode in {"invalid-json", "non-object", "invalid-utf8", "deep-json"}:
        sys.stdout.buffer.write({"invalid-json": b"{bad\n", "non-object": b"[]\n", "invalid-utf8": b"\xff\n",
                                 "deep-json": b'{"deep":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}\n'}[mode])
        sys.stdout.buffer.flush()
    else:
        value = {"request": request, "cwd": str(Path.cwd()), "environment": os.environ.get("ORKET_JSONL_FIXTURE")}
        print(json.dumps(value), end="" if mode == "no-newline" else "\n", flush=True)


def main():
    mode, root = sys.argv[1], Path(sys.argv[2])
    if mode == "blocked-write":
        (root / "first-read").touch()
        time.sleep(20)
        return 0
    requests = queue.Queue()
    reader = threading.Thread(target=_read_requests, args=(root, requests))
    reader.start()
    index = 0
    while (request := requests.get(timeout=10)) is not None:
        _respond(root, mode, index, request)
        index += 1
        if mode == "no-newline":
            # Native EOF without a newline must retain readline's accepted semantics.
            os._exit(0)
    reader.join(timeout=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
