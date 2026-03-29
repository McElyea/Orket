from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.retry_classification_policy import (
    retry_classification_policy_snapshot,
    validate_retry_classification_policy,
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
    parser = argparse.ArgumentParser(description="Check retry classification policy contract.")
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path.",
    )
    return parser.parse_args(argv)


def evaluate_retry_classification_policy() -> dict[str, Any]:
    snapshot = retry_classification_policy_snapshot()
    try:
        signals = list(validate_retry_classification_policy(snapshot))
        return {
            "schema_version": "1.0",
            "ok": True,
            "signal_count": len(signals),
            "signals": signals,
            "snapshot": snapshot,
        }
    except ValueError as exc:
        return {
            "schema_version": "1.0",
            "ok": False,
            "error": str(exc),
            "snapshot": snapshot,
        }


def validate_retry_classification_policy_report(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("E_RETRY_POLICY_REPORT_INVALID")
    if str(payload.get("schema_version") or "").strip() != "1.0":
        raise ValueError("E_RETRY_POLICY_REPORT_SCHEMA_VERSION_INVALID")

    ok = payload.get("ok")
    if not isinstance(ok, bool):
        raise ValueError("E_RETRY_POLICY_REPORT_OK_INVALID")

    snapshot = payload.get("snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("E_RETRY_POLICY_REPORT_SNAPSHOT_INVALID")
    try:
        expected_signals = list(validate_retry_classification_policy(snapshot))
    except ValueError as exc:
        raise ValueError(f"E_RETRY_POLICY_REPORT_SNAPSHOT_INVALID:{exc}") from exc

    if ok:
        signal_count = payload.get("signal_count")
        if not isinstance(signal_count, int):
            raise ValueError("E_RETRY_POLICY_REPORT_SIGNAL_COUNT_INVALID")
        signals_value = payload.get("signals")
        if not isinstance(signals_value, list):
            raise ValueError("E_RETRY_POLICY_REPORT_SIGNALS_INVALID")
        signals = [str(token).strip() for token in signals_value]
        if any(not signal for signal in signals):
            raise ValueError("E_RETRY_POLICY_REPORT_SIGNALS_INVALID")
        if signal_count != len(signals) or signal_count < 1:
            raise ValueError("E_RETRY_POLICY_REPORT_SIGNAL_COUNT_INVALID")
        if signals != expected_signals:
            raise ValueError("E_RETRY_POLICY_REPORT_SIGNAL_SET_INVALID")
        return {
            "schema_version": "1.0",
            "ok": True,
            "signal_count": signal_count,
            "signals": signals,
            "snapshot": dict(snapshot),
        }

    error = str(payload.get("error") or "").strip()
    if not error:
        raise ValueError("E_RETRY_POLICY_REPORT_ERROR_REQUIRED")
    return {
        "schema_version": "1.0",
        "ok": False,
        "error": error,
        "snapshot": dict(snapshot),
    }


def _normalized_retry_policy_report_failure(raw_payload: Any, error: str) -> dict[str, Any]:
    snapshot = retry_classification_policy_snapshot()
    if isinstance(raw_payload, dict) and isinstance(raw_payload.get("snapshot"), dict):
        raw_snapshot = dict(raw_payload["snapshot"])
        try:
            validate_retry_classification_policy(raw_snapshot)
        except ValueError:
            pass
        else:
            snapshot = raw_snapshot
    return {
        "schema_version": "1.0",
        "ok": False,
        "error": error,
        "snapshot": snapshot,
    }


def check_retry_classification_policy(*, out_path: Path | None = None) -> tuple[int, dict[str, Any]]:
    raw_payload = evaluate_retry_classification_policy()
    try:
        payload = validate_retry_classification_policy_report(raw_payload)
    except ValueError as exc:
        payload = _normalized_retry_policy_report_failure(raw_payload, str(exc))
        payload = validate_retry_classification_policy_report(payload)
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_retry_classification_policy(out_path=out_path)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
