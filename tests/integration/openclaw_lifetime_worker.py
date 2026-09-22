"""Standalone JSONL fixture; real descendants retain independently observed writes."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def main():
    root, mode, tree = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    marker = root / "adapter-ready.tmp"
    marker.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    marker.replace(root / "adapter-ready.json")
    output = None if "inherited-pipes" in sys.argv[4:] else subprocess.DEVNULL
    subprocess.Popen([sys.executable, tree, str(root), "2", *sys.argv[4:]],
                     stdin=subprocess.DEVNULL, stdout=output, stderr=output)
    request = json.loads(sys.stdin.readline())
    deadline = time.monotonic() + 20
    while not (root / "release-response").exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    if mode in {"leader-exit", "leader-failure"}:
        print(json.dumps({"index": request["index"]}), flush=True)
        return 3 if mode == "leader-failure" else 0
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
