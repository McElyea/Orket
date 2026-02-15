"""Regenerate manifest checksums for a benchmark task bank."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_tasks(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file_obj:
        payload = json.load(file_obj)
    if not isinstance(payload, list):
        raise ValueError("Task bank must be a JSON array.")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Update benchmark task-bank manifest checksums.")
    parser.add_argument("--version", default="v1", help="Benchmark version name.")
    parser.add_argument("--task-bank", default="benchmarks/task_bank/v1/tasks.json")
    parser.add_argument("--schema", default="benchmarks/task_bank/v1/schema.json")
    parser.add_argument("--out", default="benchmarks/task_bank/v1/manifest.json")
    args = parser.parse_args()

    task_bank_path = Path(args.task_bank)
    schema_path = Path(args.schema)
    out_path = Path(args.out)

    tasks = _load_tasks(task_bank_path)
    manifest = {
        "benchmark_version": args.version,
        "created_on": str(date.today()),
        "task_bank_path": str(task_bank_path).replace("\\", "/"),
        "schema_path": str(schema_path).replace("\\", "/"),
        "task_count": len(tasks),
        "task_bank_sha256": _sha256(task_bank_path),
        "schema_sha256": _sha256(schema_path),
        "id_range": ["001", f"{len(tasks):03d}"],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as file_obj:
        json.dump(manifest, file_obj, indent=2)
        file_obj.write("\n")

    print(f"[OK] Wrote manifest to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
