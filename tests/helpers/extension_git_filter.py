"""Trusted real Git smudge filter holding a marker-observable descendant tree."""
import subprocess
import sys
import time
from pathlib import Path

root, worker = Path(sys.argv[1]), Path(sys.argv[2])
subprocess.Popen([sys.executable, str(worker), str(root), "2", "detached", "ignore-term"])
deadline = time.monotonic() + 25
while not (root / "release-filter").exists() and time.monotonic() < deadline:
    time.sleep(0.01)
sys.stdout.buffer.write(sys.stdin.buffer.read())
