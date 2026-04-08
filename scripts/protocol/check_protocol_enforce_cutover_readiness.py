from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SELF_SIGNED_APPROVER = "Orket Core (local quality workspace)"

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
    from scripts.protocol.parity_projection_support import (
        invalid_projection_field_counts_present,
        merge_invalid_projection_field_counts,
        normalize_invalid_projection_field_counts,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger
    from protocol.parity_projection_support import (
        invalid_projection_field_counts_present,
        merge_invalid_projection_field_counts,
        normalize_invalid_projection_field_counts,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate enforce cutover readiness from protocol window capture manifests.",
    )
    parser.add_argument("--manifest", action="append", required=True, help="Window capture manifest path (repeatable).")
    parser.add_argument("--min-pass-windows", type=int, default=2, help="Minimum required passing windows.")
    parser.add_argument(
        "--require-distinct-window-ids",
        action="store_true",
        default=True,
        help="Require unique window ids among passing windows (default: enabled).",
    )
    parser.add_argument(
        "--no-require-distinct-window-ids",
        dest="require_distinct_window_ids",
        action="store_false",
        help="Allow duplicate window ids among passing windows.",
    )
    parser.add_argument("--out", default="", help="Optional output JSON path.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when readiness is false.")
    return parser


def _load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"manifest must be JSON object: {path}")
    return payload


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _arg_value(argv: list[Any], name: str) -> str:
    tokens = [str(item) for item in argv]
    for index, token in enumerate(tokens):
        if token == name and index + 1 < len(tokens):
            return tokens[index + 1].strip()
    return ""


def _extract_approver(payload: dict[str, Any], signoff: dict[str, Any]) -> str:
    direct = str(signoff.get("approver") or payload.get("approver") or "").strip()
    if direct:
        return direct
    for step in _as_list(payload.get("steps")):
        step_payload = _as_dict(step)
        if str(step_payload.get("name") or "").strip() != "record_window_signoff":
            continue
        approver = _arg_value(_as_list(step_payload.get("argv")), "--approver")
        if approver:
            return approver
    return ""


def _window_row(*, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    window = _as_dict(payload.get("window"))
    signoff = _as_dict(payload.get("signoff"))
    failed_steps = _as_list(payload.get("failed_steps"))
    status = str(payload.get("status") or "").strip().upper()
    schema = str(payload.get("schema_version") or "").strip()
    signoff_pass = bool(signoff.get("all_gates_passed", False))
    approver = _extract_approver(payload, signoff)
    parity_invalid_counts = normalize_invalid_projection_field_counts(signoff.get("parity_invalid_projection_field_counts"))
    rollout_invalid_counts = normalize_invalid_projection_field_counts(
        signoff.get("rollout_parity_invalid_projection_field_counts")
    )
    row = {
        "path": str(path).replace("\\", "/"),
        "schema_version": schema,
        "window_id": str(window.get("id") or "").strip(),
        "window_date": str(window.get("date") or "").strip(),
        "status": status,
        "failed_steps": [str(item) for item in failed_steps],
        "failed_step_count": len(failed_steps),
        "signoff_all_gates_passed": signoff_pass,
        "approver": approver,
        "parity_invalid_projection_field_counts": parity_invalid_counts,
        "rollout_parity_invalid_projection_field_counts": rollout_invalid_counts,
        "passes": status == "PASS" and signoff_pass and len(failed_steps) == 0,
    }
    return row


def _evaluate_rows(
    *,
    rows: list[dict[str, Any]],
    min_pass_windows: int,
    require_distinct_window_ids: bool,
) -> dict[str, Any]:
    passing = [row for row in rows if bool(row.get("passes"))]
    approvers = [str(row.get("approver") or "").strip() for row in rows if str(row.get("approver") or "").strip()]
    passing_ids = [str(row.get("window_id") or "") for row in passing if str(row.get("window_id") or "").strip()]
    distinct_ids = sorted({token for token in passing_ids if token})
    invalid_projection_rows = [
        row
        for row in rows
        if invalid_projection_field_counts_present(
            normalize_invalid_projection_field_counts(row.get("parity_invalid_projection_field_counts"))
        )
        or invalid_projection_field_counts_present(
            normalize_invalid_projection_field_counts(row.get("rollout_parity_invalid_projection_field_counts"))
        )
    ]
    errors: list[str] = []
    if len(passing) < int(min_pass_windows):
        errors.append(f"passing_windows={len(passing)} < min_pass_windows={int(min_pass_windows)}")
    if require_distinct_window_ids and len(distinct_ids) < int(min_pass_windows):
        errors.append(
            "distinct_passing_window_ids="
            f"{len(distinct_ids)} < min_pass_windows={int(min_pass_windows)}"
        )
    unknown_schema = [row for row in rows if str(row.get("schema_version") or "") != "protocol_enforce_window_capture_manifest.v1"]
    if unknown_schema:
        errors.append(f"unexpected_schema_count={len(unknown_schema)}")
    return {
        "ready": len(errors) == 0,
        "errors": errors,
        "passing_windows": len(passing),
        "distinct_passing_window_ids": len(distinct_ids),
        "passing_window_ids": distinct_ids,
        "self_attested_only": bool(approvers) and all(approver == SELF_SIGNED_APPROVER for approver in approvers),
        "windows_with_invalid_projection_counts": len(invalid_projection_rows),
        "parity_invalid_projection_field_counts": merge_invalid_projection_field_counts(
            rows, "parity_invalid_projection_field_counts"
        ),
        "rollout_parity_invalid_projection_field_counts": merge_invalid_projection_field_counts(
            rows, "rollout_parity_invalid_projection_field_counts"
        ),
    }


def evaluate_cutover_readiness(
    *,
    manifest_paths: list[Path],
    min_pass_windows: int,
    require_distinct_window_ids: bool,
) -> dict[str, Any]:
    rows = [_window_row(path=path, payload=_load_manifest(path)) for path in manifest_paths]
    verdict = _evaluate_rows(
        rows=rows,
        min_pass_windows=max(1, int(min_pass_windows)),
        require_distinct_window_ids=bool(require_distinct_window_ids),
    )
    return {
        "schema_version": "protocol_enforce_cutover_readiness.v1",
        "manifest_count": len(manifest_paths),
        "min_pass_windows": max(1, int(min_pass_windows)),
        "require_distinct_window_ids": bool(require_distinct_window_ids),
        "windows": rows,
        "ready": bool(verdict["ready"]),
        "errors": list(verdict["errors"]),
        "passing_windows": int(verdict["passing_windows"]),
        "distinct_passing_window_ids": int(verdict["distinct_passing_window_ids"]),
        "passing_window_ids": list(verdict["passing_window_ids"]),
        "self_attested_only": bool(verdict["self_attested_only"]),
        "windows_with_invalid_projection_counts": int(verdict["windows_with_invalid_projection_counts"]),
        "parity_invalid_projection_field_counts": dict(verdict["parity_invalid_projection_field_counts"]),
        "rollout_parity_invalid_projection_field_counts": dict(
            verdict["rollout_parity_invalid_projection_field_counts"]
        ),
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    manifest_paths = [Path(str(token)).resolve() for token in list(args.manifest or [])]
    payload = evaluate_cutover_readiness(
        manifest_paths=manifest_paths,
        min_pass_windows=int(args.min_pass_windows),
        require_distinct_window_ids=bool(args.require_distinct_window_ids),
    )
    out_raw = str(args.out or "").strip()
    if out_raw:
        write_payload_with_diff_ledger(Path(out_raw).resolve(), payload)
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", end="")
    if bool(args.strict) and not bool(payload.get("ready")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
