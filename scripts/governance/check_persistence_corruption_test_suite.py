from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.adapters.storage.protocol_append_only_ledger import (
    AppendOnlyRunLedger,
    LedgerFramingError,
    encode_lpj_c32_record,
)
from orket.runtime.persistence_corruption_test_contract import (
    persistence_corruption_test_contract_snapshot,
    validate_persistence_corruption_test_contract,
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
    parser = argparse.ArgumentParser(description="Check persistence corruption test suite contract.")
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path.",
    )
    return parser.parse_args(argv)


def _assert_raises_ledger_error(check_id: str, expected_error_code: str, action: Any) -> tuple[bool, str]:
    try:
        action()
    except LedgerFramingError as exc:
        code = str(exc.code or "").strip()
        return code == expected_error_code, code
    return False, ""


def _run_checksum_corruption_check(path: Path) -> tuple[bool, dict[str, Any]]:
    first = encode_lpj_c32_record({"event_seq": 1, "kind": "ok"})
    broken = bytearray(encode_lpj_c32_record({"event_seq": 2, "kind": "bad"}))
    broken[-1] = broken[-1] ^ 0xFF
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(first + bytes(broken))
    ledger = AppendOnlyRunLedger(path)
    ok, observed_error_code = _assert_raises_ledger_error(
        "checksum_corruption_rejected",
        "E_LEDGER_CORRUPT",
        ledger.replay_events,
    )
    return ok, {"observed_error_code": observed_error_code}


def _run_non_monotonic_sequence_check(path: Path) -> tuple[bool, dict[str, Any]]:
    stream = (
        encode_lpj_c32_record({"event_seq": 1, "kind": "a"})
        + encode_lpj_c32_record({"event_seq": 3, "kind": "b"})
        + encode_lpj_c32_record({"event_seq": 2, "kind": "c"})
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(stream)
    ledger = AppendOnlyRunLedger(path)
    ok, observed_error_code = _assert_raises_ledger_error(
        "non_monotonic_sequence_rejected",
        "E_LEDGER_SEQ",
        ledger.replay_events,
    )
    return ok, {"observed_error_code": observed_error_code}


def _run_partial_tail_safe_recovery_check(path: Path) -> tuple[bool, dict[str, Any]]:
    first = encode_lpj_c32_record({"event_seq": 1, "kind": "run_started"})
    second = encode_lpj_c32_record({"event_seq": 2, "kind": "run_finished"})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(first + second[:-3])
    ledger = AppendOnlyRunLedger(path)
    replayed = ledger.replay_events()
    ok = len(replayed) == 1 and int(replayed[0].get("event_seq") or 0) == 1
    return ok, {"replayed_event_count": len(replayed)}


def evaluate_persistence_corruption_test_suite() -> dict[str, Any]:
    contract = persistence_corruption_test_contract_snapshot()
    try:
        check_ids = list(validate_persistence_corruption_test_contract(contract))
    except ValueError as exc:
        return {
            "schema_version": "1.0",
            "ok": False,
            "error": str(exc),
            "contract": contract,
        }

    check_map = {
        "checksum_corruption_rejected": _run_checksum_corruption_check,
        "non_monotonic_sequence_rejected": _run_non_monotonic_sequence_check,
        "partial_tail_replayed_safely": _run_partial_tail_safe_recovery_check,
    }
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="persistence-corruption-check-") as tmp_dir:
        root = Path(tmp_dir)
        for check_id in check_ids:
            evaluator = check_map[check_id]
            path = root / f"{check_id}.log"
            ok, detail = evaluator(path)
            checks.append(
                {
                    "check": check_id,
                    "ok": bool(ok),
                    **detail,
                }
            )

    return {
        "schema_version": "1.0",
        "ok": all(bool(row.get("ok")) for row in checks),
        "check_count": len(check_ids),
        "checks": checks,
        "contract": contract,
    }


def check_persistence_corruption_test_suite(*, out_path: Path | None = None) -> tuple[int, dict[str, Any]]:
    payload = evaluate_persistence_corruption_test_suite()
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_persistence_corruption_test_suite(out_path=out_path)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
