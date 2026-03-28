from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
import sys
from typing import Any

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
    from scripts.protocol.parity_projection_support import (
        extract_campaign_invalid_projection_field_counts,
        render_invalid_projection_field_counts_detail,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger
    from protocol.parity_projection_support import (
        extract_campaign_invalid_projection_field_counts,
        render_invalid_projection_field_counts_detail,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record enforce-phase rollout sign-off for a campaign window.",
    )
    parser.add_argument("--window-id", required=True, help="Window identifier (for example window_a).")
    parser.add_argument("--window-date", required=True, help="Window date (for example 2026-03-05).")
    parser.add_argument("--replay-campaign", required=True, help="Path to replay campaign artifact JSON.")
    parser.add_argument("--parity-campaign", required=True, help="Path to parity campaign artifact JSON.")
    parser.add_argument("--rollout-bundle", required=True, help="Path to rollout bundle JSON.")
    parser.add_argument("--error-summary", required=True, help="Path to protocol error summary JSON.")
    parser.add_argument(
        "--retry-spike-status",
        choices=["pass", "fail", "unknown"],
        default="unknown",
        help="Operator-observed retry spike gate status.",
    )
    parser.add_argument(
        "--allow-error-family",
        action="append",
        default=[],
        help="Error family allowed to be present without failing the gate (repeatable).",
    )
    parser.add_argument("--approver", default="", help="Approver label.")
    parser.add_argument("--notes", default="", help="Optional operator notes.")
    parser.add_argument("--out", default="", help="Optional output JSON path.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero unless all sign-off gates pass.")
    return parser


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return payload


def _gate(*, passed: bool, detail: str) -> dict[str, Any]:
    return {"passed": bool(passed), "detail": str(detail)}


def _error_gate(
    *,
    error_summary: dict[str, Any],
    allowed_families: set[str],
) -> tuple[bool, str, dict[str, int]]:
    raw_family_counts = error_summary.get("family_counts")
    family_counts: dict[str, int] = {}
    if isinstance(raw_family_counts, dict):
        for key, value in raw_family_counts.items():
            token = str(key or "").strip()
            if not token:
                continue
            family_counts[token] = int(value or 0)
    blocking = {
        family: count
        for family, count in family_counts.items()
        if count > 0 and family not in allowed_families
    }
    unregistered_count = int(error_summary.get("unregistered_count") or 0)
    passed = unregistered_count == 0 and not blocking
    if not passed:
        return (
            False,
            f"unregistered_count={unregistered_count}, blocking_families={sorted(blocking)}",
            {key: int(blocking[key]) for key in sorted(blocking)},
        )
    return True, "no blocking or unregistered error families", {}


def build_signoff_payload(
    *,
    window_id: str,
    window_date: str,
    replay_campaign_path: Path,
    parity_campaign_path: Path,
    rollout_bundle_path: Path,
    error_summary_path: Path,
    retry_spike_status: str,
    allowed_error_families: set[str],
    approver: str,
    notes: str,
) -> dict[str, Any]:
    replay_campaign = _load_json_object(replay_campaign_path, label="replay campaign")
    parity_campaign = _load_json_object(parity_campaign_path, label="parity campaign")
    rollout_bundle = _load_json_object(rollout_bundle_path, label="rollout bundle")
    error_summary = _load_json_object(error_summary_path, label="error summary")
    parity_invalid_projection_field_counts = extract_campaign_invalid_projection_field_counts(parity_campaign)
    rollout_parity_invalid_projection_field_counts = extract_campaign_invalid_projection_field_counts(
        dict(rollout_bundle.get("ledger_parity_campaign") or {})
    )

    replay_ok = bool(replay_campaign.get("all_match") is True)
    parity_ok = bool(parity_campaign.get("all_match") is True)
    rollout_ok = bool(rollout_bundle.get("strict_ok") is True)
    retry_ok = str(retry_spike_status) == "pass"
    error_ok, error_detail, blocking_families = _error_gate(
        error_summary=error_summary,
        allowed_families=allowed_error_families,
    )
    approver_ok = bool(str(approver or "").strip())

    gates = {
        "replay_all_match": _gate(passed=replay_ok, detail=f"all_match={replay_campaign.get('all_match')}"),
        "parity_all_match": _gate(
            passed=parity_ok,
            detail=render_invalid_projection_field_counts_detail(
                prefix="all_match",
                value=parity_campaign.get("all_match"),
                counts=parity_invalid_projection_field_counts,
            ),
        ),
        "rollout_bundle_strict_ok": _gate(
            passed=rollout_ok,
            detail=render_invalid_projection_field_counts_detail(
                prefix="strict_ok",
                value=rollout_bundle.get("strict_ok"),
                counts=rollout_parity_invalid_projection_field_counts,
            ),
        ),
        "error_summary_clean": _gate(passed=error_ok, detail=error_detail),
        "retry_spike_check": _gate(passed=retry_ok, detail=f"retry_spike_status={retry_spike_status}"),
        "approver_present": _gate(passed=approver_ok, detail="approver supplied" if approver_ok else "approver missing"),
    }
    all_passed = all(bool(item.get("passed")) for item in gates.values())
    return {
        "schema_version": "protocol_enforce_window_signoff.v1",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "window": {
            "id": str(window_id),
            "date": str(window_date),
        },
        "artifacts": {
            "replay_campaign": str(replay_campaign_path).replace("\\", "/"),
            "parity_campaign": str(parity_campaign_path).replace("\\", "/"),
            "rollout_bundle": str(rollout_bundle_path).replace("\\", "/"),
            "error_summary": str(error_summary_path).replace("\\", "/"),
        },
        "allowed_error_families": sorted(allowed_error_families),
        "blocking_error_families": blocking_families,
        "parity_invalid_projection_field_counts": parity_invalid_projection_field_counts,
        "rollout_parity_invalid_projection_field_counts": rollout_parity_invalid_projection_field_counts,
        "retry_spike_status": str(retry_spike_status),
        "approver": str(approver or ""),
        "notes": str(notes or ""),
        "gates": gates,
        "all_gates_passed": all_passed,
        "gate_status": "PASS" if all_passed else "FAIL",
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = build_signoff_payload(
        window_id=str(args.window_id),
        window_date=str(args.window_date),
        replay_campaign_path=Path(str(args.replay_campaign)).resolve(),
        parity_campaign_path=Path(str(args.parity_campaign)).resolve(),
        rollout_bundle_path=Path(str(args.rollout_bundle)).resolve(),
        error_summary_path=Path(str(args.error_summary)).resolve(),
        retry_spike_status=str(args.retry_spike_status),
        allowed_error_families={str(token).strip() for token in list(args.allow_error_family or []) if str(token).strip()},
        approver=str(args.approver or "").strip(),
        notes=str(args.notes or "").strip(),
    )
    out_raw = str(args.out or "").strip()
    if out_raw:
        write_payload_with_diff_ledger(Path(out_raw).resolve(), payload)
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", end="")
    if bool(args.strict) and not bool(payload.get("all_gates_passed")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
