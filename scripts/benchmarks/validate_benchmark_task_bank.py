"""Validate a versioned Orket benchmark task bank."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from jsonschema import ValidationError, validate

EXPECTED_TIER_COUNTS = {
    1: 15,
    2: 20,
    3: 25,
    4: 15,
    5: 20,
    6: 5,
}


def _load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def _validate_ids(tasks: list[dict]) -> None:
    ids = [task["id"] for task in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate task IDs found in task bank.")

    expected_ids = [f"{index:03d}" for index in range(1, len(tasks) + 1)]
    if ids != expected_ids:
        raise ValueError(
            "Task IDs must be contiguous and ordered from 001 to "
            f"{expected_ids[-1]} (current ordering is invalid)."
        )


def _validate_tier_counts(tasks: list[dict]) -> None:
    counts = Counter(task["tier"] for task in tasks)
    if counts != EXPECTED_TIER_COUNTS:
        raise ValueError(
            f"Tier distribution mismatch. Expected {EXPECTED_TIER_COUNTS}, found {dict(counts)}."
        )


def validate_task_bank(task_bank_path: Path, schema_path: Path) -> None:
    raw_tasks = _load_json(task_bank_path)
    if not isinstance(raw_tasks, list):
        raise ValueError("Task bank must be a JSON array.")

    schema = _load_json(schema_path)
    try:
        validate(instance=raw_tasks, schema=schema)
    except ValidationError as error:
        path = ".".join(str(part) for part in error.absolute_path)
        raise ValueError(f"Schema validation failed at '{path}': {error.message}") from error

    tasks: list[dict] = raw_tasks
    _validate_ids(tasks)
    _validate_tier_counts(tasks)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate benchmark task-bank files.")
    parser.add_argument(
        "--task-bank",
        default="benchmarks/task_bank/v1/tasks.json",
        help="Path to task bank JSON file.",
    )
    parser.add_argument(
        "--schema",
        default="benchmarks/task_bank/v1/schema.json",
        help="Path to task bank JSON schema file.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    task_bank_path = Path(args.task_bank)
    schema_path = Path(args.schema)

    try:
        validate_task_bank(task_bank_path=task_bank_path, schema_path=schema_path)
    except (OSError, ValueError) as error:
        print(f"[FAIL] {error}")
        return 1

    print(
        "[PASS] Task bank is valid: "
        f"{task_bank_path} (schema: {schema_path})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
