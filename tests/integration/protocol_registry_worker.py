"""Standalone native registry writer used by process-level storage proof."""
import json
import sys
import time
from pathlib import Path

from orket.adapters.storage.operation_commit_registry import OperationCommitRegistry
from orket.core.contracts.local_file_lock import LocalFileLockError


def main():
    path, operation_id, digest, mode = sys.argv[1:]
    registry = OperationCommitRegistry(Path(path))
    original = registry._persist

    def held(entries):
        Path(path + ".ready").write_text("ready", encoding="utf-8")
        deadline = time.monotonic() + 15
        while not Path(path + ".release").exists():
            if time.monotonic() > deadline:
                raise TimeoutError("native registry release was not supplied")
            time.sleep(0.01)
        original(entries)

    if mode == "hold":
        registry._persist = held
    try:
        result = registry.commit(operation_id=operation_id, event_seq=1 if mode == "hold" else 2, entry_digest=digest)
    except LocalFileLockError as exc:
        print(json.dumps({"status": "busy", "error": str(exc)}))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
