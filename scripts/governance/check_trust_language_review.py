from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.trust_language_review_policy import (
    classify_trust_language_phrase,
    trust_language_review_policy_snapshot,
    validate_trust_language_review_policy,
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
    parser = argparse.ArgumentParser(description="Check trust language review policy.")
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path.",
    )
    return parser.parse_args(argv)


def evaluate_trust_language_review() -> dict[str, Any]:
    policy = trust_language_review_policy_snapshot()
    try:
        claims = list(validate_trust_language_review_policy(policy))
    except ValueError as exc:
        return {
            "schema_version": "1.0",
            "ok": False,
            "error": str(exc),
            "policy": policy,
        }

    checks = [
        {
            "check": "saved_phrase_without_qualifier_is_unqualified",
            "ok": classify_trust_language_phrase("saved", policy=policy) == "unqualified",
        },
        {
            "check": "saved_phrase_with_receipt_is_qualified",
            "ok": classify_trust_language_phrase("saved with durable receipt", policy=policy) == "qualified",
        },
        {
            "check": "verified_phrase_with_sources_is_qualified",
            "ok": classify_trust_language_phrase("verified with cited sources", policy=policy) == "qualified",
        },
    ]
    return {
        "schema_version": "1.0",
        "ok": all(bool(row.get("ok")) for row in checks),
        "claim_count": len(claims),
        "checks": checks,
        "policy": policy,
    }


def check_trust_language_review(*, out_path: Path | None = None) -> tuple[int, dict[str, Any]]:
    payload = evaluate_trust_language_review()
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_trust_language_review(out_path=out_path)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
