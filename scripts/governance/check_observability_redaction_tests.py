from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.extensions.workload_artifacts import WorkloadArtifacts
from orket.runtime.observability_redaction_test_contract import (
    observability_redaction_test_contract_snapshot,
    validate_observability_redaction_test_contract,
)
from scripts.common.evidence_environment import redact_env_value

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
    parser = argparse.ArgumentParser(description="Check observability redaction tests.")
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path.",
    )
    return parser.parse_args(argv)


def evaluate_observability_redaction_tests() -> dict[str, Any]:
    contract = observability_redaction_test_contract_snapshot()
    try:
        check_ids = list(validate_observability_redaction_test_contract(contract))
    except ValueError as exc:
        return {
            "schema_version": "1.0",
            "ok": False,
            "error": str(exc),
            "contract": contract,
        }

    checks: list[dict[str, Any]] = []

    secret_masked = redact_env_value("ORKET_API_KEY", "secret-token-value")
    checks.append(
        {
            "check": "env_secret_values_masked",
            "ok": secret_masked == "<redacted>",
            "observed": secret_masked,
        }
    )

    preserved = redact_env_value("ORKET_HOST", "localhost")
    checks.append(
        {
            "check": "env_non_secret_values_preserved",
            "ok": preserved == "localhost",
            "observed": preserved,
        }
    )

    long_value = "x" * 300
    truncated = redact_env_value("ORKET_HOST", long_value)
    checks.append(
        {
            "check": "env_long_values_truncated",
            "ok": len(truncated) == 256 and truncated.endswith("..."),
            "observed_length": len(truncated),
            "observed_suffix": truncated[-3:],
        }
    )

    redacted_snapshot = WorkloadArtifacts._redacted_snapshot({"api_key": "secret", "status": "ok"})
    checks.append(
        {
            "check": "workload_snapshot_redaction_shape",
            "ok": set(redacted_snapshot.keys()) == {"keys", "item_count", "payload_digest_sha256"},
            "observed_keys": sorted(redacted_snapshot.keys()),
        }
    )

    return {
        "schema_version": "1.0",
        "ok": all(bool(row.get("ok")) for row in checks),
        "check_count": len(check_ids),
        "checks": checks,
        "contract": contract,
    }


def check_observability_redaction_tests(*, out_path: Path | None = None) -> tuple[int, dict[str, Any]]:
    payload = evaluate_observability_redaction_tests()
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_observability_redaction_tests(out_path=out_path)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
