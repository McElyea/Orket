from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.naming_discipline_policy import (
    naming_discipline_policy_snapshot,
    validate_naming_discipline_policy,
)
from orket.runtime.run_start_contract_artifacts import CONTRACT_SNAPSHOT_DEFS

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - script execution fallback
    import importlib.util

    helper_path = Path(__file__).resolve().parents[1] / "common" / "rerun_diff_ledger.py"
    spec = importlib.util.spec_from_file_location("rerun_diff_ledger", helper_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive fallback
        raise RuntimeError(f"E_DIFF_LEDGER_HELPER_LOAD_FAILED:{helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    write_payload_with_diff_ledger = module.write_payload_with_diff_ledger


_SNAKE_CASE_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check naming discipline policy.")
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path.",
    )
    return parser.parse_args(argv)


def _is_snake_case(token: str) -> bool:
    return bool(_SNAKE_CASE_RE.match(token))


def evaluate_naming_discipline_policy() -> dict[str, Any]:
    policy = naming_discipline_policy_snapshot()
    try:
        convention_ids = list(validate_naming_discipline_policy(policy))
    except ValueError as exc:
        return {
            "schema_version": "1.0",
            "ok": False,
            "error": str(exc),
            "policy": policy,
        }

    findings: list[dict[str, str]] = []

    for artifact_key, filename, _factory, _error_code in CONTRACT_SNAPSHOT_DEFS:
        key = str(artifact_key).strip()
        name = str(filename).strip()
        if not _is_snake_case(key):
            findings.append(
                {
                    "check": "artifact_keys_snake_case",
                    "issue": f"non_snake_case_artifact_key:{key}",
                }
            )
        expected_filename = f"{key}.json"
        if name != expected_filename:
            findings.append(
                {
                    "check": "artifact_filenames_match_keys",
                    "issue": f"filename_mismatch:{key}:{name}:{expected_filename}",
                }
            )

    governance_dir = REPO_ROOT / "scripts" / "governance"
    for path in sorted(governance_dir.glob("check_*.py")):
        stem = path.stem
        if not _is_snake_case(stem):
            findings.append(
                {
                    "check": "governance_checker_scripts_snake_case",
                    "issue": f"non_snake_case_checker_script:{path.name}",
                }
            )

    return {
        "schema_version": "1.0",
        "ok": not findings,
        "convention_count": len(convention_ids),
        "findings": findings,
        "policy": policy,
    }


def check_naming_discipline_policy(*, out_path: Path | None = None) -> tuple[int, dict[str, Any]]:
    payload = evaluate_naming_discipline_policy()
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_naming_discipline_policy(out_path=out_path)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
