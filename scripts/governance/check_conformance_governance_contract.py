from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.conformance_governance_contract import (
    conformance_governance_contract_snapshot,
    validate_conformance_governance_contract,
)

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


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check truthful runtime conformance governance contract.")
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path.",
    )
    return parser.parse_args(argv)


def evaluate_conformance_governance_contract() -> dict[str, Any]:
    snapshot = conformance_governance_contract_snapshot()
    try:
        section_ids = list(validate_conformance_governance_contract(snapshot))
    except ValueError as exc:
        return {
            "schema_version": "1.0",
            "ok": False,
            "error": str(exc),
            "snapshot": snapshot,
        }

    checks = [
        {
            "check": "golden_transcript_diff_mode_controlled",
            "ok": any(
                str(row.get("section_id") or "").strip() == "golden_transcript_diff_policy"
                and str(row.get("diff_mode") or "").strip() == "controlled"
                for row in snapshot.get("sections", [])
                if isinstance(row, dict)
            ),
        },
        {
            "check": "operator_signoff_requires_operator_action",
            "ok": any(
                str(row.get("section_id") or "").strip() == "operator_signoff_bundle"
                and str(row.get("required_operator_action_when_eligible") or "").strip()
                == "operator_signoff_required"
                for row in snapshot.get("sections", [])
                if isinstance(row, dict)
            ),
        },
        {
            "check": "repo_introspection_uses_workspace_and_capability_artifacts",
            "ok": any(
                str(row.get("section_id") or "").strip() == "repo_introspection_report"
                and set(str(token).strip() for token in row.get("source_artifacts", []) if str(token).strip())
                == {"workspace_state_snapshot", "capability_manifest"}
                for row in snapshot.get("sections", [])
                if isinstance(row, dict)
            ),
        },
    ]
    return {
        "schema_version": "1.0",
        "ok": all(bool(row.get("ok")) for row in checks),
        "section_count": len(section_ids),
        "checks": checks,
        "snapshot": snapshot,
    }


def check_conformance_governance_contract(*, out_path: Path | None = None) -> tuple[int, dict[str, Any]]:
    payload = evaluate_conformance_governance_contract()
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_conformance_governance_contract(out_path=out_path)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
