"""Owned acceptance fixture: a bounded process tree with independently visible writes."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def main() -> None:
    root, depth = Path(sys.argv[1]), int(sys.argv[2])
    flags = sys.argv[3:]
    if "ignore-term" in flags and os.name != "nt":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    child = None
    if depth:
        options = {}
        if "detached" in flags:
            options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        child = subprocess.Popen([sys.executable, __file__, str(root), str(depth - 1), *flags], **options)
    ready = root / f"ready-{depth}.tmp"
    ready.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    ready.replace(root / f"ready-{depth}.json")
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if depth == 2 and {"leader-exit", "leader-failure"}.intersection(flags) and (root / "release-leader").exists():
            raise SystemExit(7 if "leader-failure" in flags else 0)
        with (root / f"heartbeat-{depth}.txt").open("a", encoding="utf-8") as stream:
            stream.write("alive\n")
        time.sleep(0.05)
    if child:
        child.wait(timeout=5)


if __name__ == "__main__":
    main()
