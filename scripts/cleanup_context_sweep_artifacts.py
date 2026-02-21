from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cleanup ephemeral context sweep artifacts.")
    parser.add_argument("--out-dir", required=True, help="Context sweep output directory.")
    parser.add_argument("--dry-run", action="store_true", help="Report only; do not delete.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    out_dir = Path(args.out_dir)
    target = out_dir / ".storage"
    removed: list[str] = []
    skipped: list[str] = []

    if target.exists() and target.is_dir():
        removed.append(str(target).replace("\\", "/"))
        if not bool(args.dry_run):
            shutil.rmtree(target)
    else:
        skipped.append(str(target).replace("\\", "/"))

    report = {
        "status": "OK",
        "out_dir": str(out_dir).replace("\\", "/"),
        "dry_run": bool(args.dry_run),
        "removed": removed,
        "skipped": skipped,
        "note": "Persistent orket_storage data is never removed by this command.",
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
