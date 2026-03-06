from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import sys
from time import perf_counter
from typing import Any, Callable

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
    from scripts.protocol.publish_protocol_rollout_artifacts import main as publish_rollout_artifacts_main
    from scripts.protocol.record_protocol_enforce_window_signoff import main as record_window_signoff_main
    from scripts.protocol.run_protocol_determinism_campaign import main as run_determinism_campaign_main
    from scripts.protocol.run_protocol_ledger_parity_campaign import main as run_ledger_parity_campaign_main
    from scripts.protocol.summarize_protocol_error_codes import main as summarize_error_codes_main
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger
    from protocol.publish_protocol_rollout_artifacts import main as publish_rollout_artifacts_main
    from protocol.record_protocol_enforce_window_signoff import main as record_window_signoff_main
    from protocol.run_protocol_determinism_campaign import main as run_determinism_campaign_main
    from protocol.run_protocol_ledger_parity_campaign import main as run_ledger_parity_campaign_main
    from protocol.summarize_protocol_error_codes import main as summarize_error_codes_main


DEFAULT_OUT_ROOT = Path("benchmarks/results/protocol/protocol_governed/enforce_phase")
DEFAULT_SQLITE_SUFFIX = Path(".orket") / "durable" / "db" / "orket_persistence.db"
DEFAULT_RUNS_SUFFIX = Path("runs")


@dataclass(frozen=True)
class WindowCapturePaths:
    out_root: Path
    replay_campaign: Path
    parity_campaign: Path
    rollout_out_dir: Path
    rollout_bundle: Path
    error_summary: Path
    signoff: Path
    manifest: Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one-command enforce window capture with operator sign-off.")
    parser.add_argument("--window-id", required=True, help="Window identifier (for example window_prod_a).")
    parser.add_argument("--window-date", required=True, help="Window date (for example 2026-03-06).")
    parser.add_argument("--workspace-root", default=".", help="Workspace root containing runs/ and .orket/")
    parser.add_argument("--runs-root", default="", help="Optional override for runs root.")
    parser.add_argument("--sqlite-db", default="", help="Optional override for sqlite DB path.")
    parser.add_argument("--run-id", required=True, help="Replay campaign run id and baseline run id.")
    parser.add_argument("--session-id", default="", help="Parity campaign session id (defaults to --run-id).")
    parser.add_argument("--retry-spike-status", choices=["pass", "fail", "unknown"], required=True)
    parser.add_argument("--approver", required=True, help="Operator approver label.")
    parser.add_argument("--notes", default="", help="Optional operator notes.")
    parser.add_argument("--allow-error-family", action="append", default=[], help="Allowed error family (repeatable).")
    parser.add_argument("--out-root", default="", help="Window output root. Defaults under enforce_phase/<window-id>.")
    parser.add_argument("--strict", action="store_true", help="Pass strict mode to all sub-steps.")
    return parser


def _resolve_path(workspace_root: Path, override: str, default_suffix: Path) -> Path:
    token = str(override or "").strip()
    if token:
        return Path(token).resolve()
    return (workspace_root / default_suffix).resolve()


def _resolve_window_paths(*, out_root: str, window_id: str) -> WindowCapturePaths:
    base_root = Path(str(out_root).strip()).resolve() if str(out_root).strip() else (DEFAULT_OUT_ROOT / window_id).resolve()
    return WindowCapturePaths(
        out_root=base_root,
        replay_campaign=base_root / "protocol_replay_campaign.json",
        parity_campaign=base_root / "protocol_ledger_parity_campaign.json",
        rollout_out_dir=base_root / "rollout_artifacts",
        rollout_bundle=base_root / "rollout_artifacts" / "protocol_rollout_bundle.latest.json",
        error_summary=base_root / "protocol_error_code_summary.json",
        signoff=base_root / "protocol_operator_signoff.json",
        manifest=base_root / "protocol_window_capture_manifest.json",
    )


def _invoke_step(*, name: str, runner: Callable[[list[str] | None], int], argv: list[str]) -> dict[str, Any]:
    started = perf_counter()
    exit_code = int(runner(argv))
    return {
        "name": name,
        "argv": list(argv),
        "exit_code": exit_code,
        "elapsed_ms": int((perf_counter() - started) * 1000),
    }


def _strict_flag(enabled: bool) -> list[str]:
    return ["--strict"] if enabled else []


def _build_determinism_argv(*, runs_root: Path, run_id: str, out_path: Path, strict: bool) -> list[str]:
    return ["--runs-root", str(runs_root), "--run-id", run_id, "--baseline-run-id", run_id, "--out", str(out_path), *_strict_flag(strict)]


def _build_parity_argv(*, sqlite_db: Path, workspace_root: Path, session_id: str, out_path: Path, strict: bool) -> list[str]:
    return [
        "--sqlite-db",
        str(sqlite_db),
        "--protocol-root",
        str(workspace_root),
        "--session-id",
        session_id,
        "--out",
        str(out_path),
        *_strict_flag(strict),
    ]


def _build_publish_argv(*, workspace_root: Path, runs_root: Path, sqlite_db: Path, run_id: str, session_id: str, out_dir: Path, strict: bool) -> list[str]:
    return [
        "--workspace-root",
        str(workspace_root),
        "--runs-root",
        str(runs_root),
        "--sqlite-db",
        str(sqlite_db),
        "--run-id",
        run_id,
        "--session-id",
        session_id,
        "--baseline-run-id",
        run_id,
        "--out-dir",
        str(out_dir),
        *_strict_flag(strict),
    ]


def _build_summary_argv(*, replay_path: Path, parity_path: Path, out_path: Path, strict: bool) -> list[str]:
    return ["--input", str(replay_path), "--input", str(parity_path), "--out", str(out_path), *_strict_flag(strict)]


def _build_signoff_argv(
    *,
    window_id: str,
    window_date: str,
    paths: WindowCapturePaths,
    retry_spike_status: str,
    approver: str,
    notes: str,
    allow_error_families: list[str],
    strict: bool,
) -> list[str]:
    argv = [
        "--window-id",
        window_id,
        "--window-date",
        window_date,
        "--replay-campaign",
        str(paths.replay_campaign),
        "--parity-campaign",
        str(paths.parity_campaign),
        "--rollout-bundle",
        str(paths.rollout_bundle),
        "--error-summary",
        str(paths.error_summary),
        "--retry-spike-status",
        retry_spike_status,
        "--approver",
        approver,
        "--notes",
        notes,
        "--out",
        str(paths.signoff),
        *_strict_flag(strict),
    ]
    for family in allow_error_families:
        argv.extend(["--allow-error-family", family])
    return argv


def _execute_capture_steps(
    *,
    runs_root: Path,
    sqlite_db: Path,
    workspace_root: Path,
    run_id: str,
    session_id: str,
    window_id: str,
    window_date: str,
    paths: WindowCapturePaths,
    retry_spike_status: str,
    approver: str,
    notes: str,
    allow_error_families: list[str],
    strict: bool,
) -> list[dict[str, Any]]:
    steps = [
        (
            "determinism_campaign",
            run_determinism_campaign_main,
            _build_determinism_argv(runs_root=runs_root, run_id=run_id, out_path=paths.replay_campaign, strict=strict),
        ),
        (
            "ledger_parity_campaign",
            run_ledger_parity_campaign_main,
            _build_parity_argv(sqlite_db=sqlite_db, workspace_root=workspace_root, session_id=session_id, out_path=paths.parity_campaign, strict=strict),
        ),
        (
            "publish_rollout_bundle",
            publish_rollout_artifacts_main,
            _build_publish_argv(
                workspace_root=workspace_root,
                runs_root=runs_root,
                sqlite_db=sqlite_db,
                run_id=run_id,
                session_id=session_id,
                out_dir=paths.rollout_out_dir,
                strict=strict,
            ),
        ),
        (
            "summarize_error_codes",
            summarize_error_codes_main,
            _build_summary_argv(replay_path=paths.replay_campaign, parity_path=paths.parity_campaign, out_path=paths.error_summary, strict=strict),
        ),
        (
            "record_window_signoff",
            record_window_signoff_main,
            _build_signoff_argv(
                window_id=window_id,
                window_date=window_date,
                paths=paths,
                retry_spike_status=retry_spike_status,
                approver=approver,
                notes=notes,
                allow_error_families=allow_error_families,
                strict=strict,
            ),
        ),
    ]
    return [_invoke_step(name=name, runner=runner, argv=argv) for name, runner, argv in steps]


def _load_signoff(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid signoff payload shape: {path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    workspace_root = Path(str(args.workspace_root)).resolve()
    runs_root = _resolve_path(workspace_root, str(args.runs_root), DEFAULT_RUNS_SUFFIX)
    sqlite_db = _resolve_path(workspace_root, str(args.sqlite_db), DEFAULT_SQLITE_SUFFIX)
    run_id = str(args.run_id).strip()
    session_id = str(args.session_id).strip() or run_id
    allow_families = [str(token).strip() for token in list(args.allow_error_family or []) if str(token).strip()]
    paths = _resolve_window_paths(out_root=str(args.out_root), window_id=str(args.window_id))
    paths.out_root.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    steps = _execute_capture_steps(
        runs_root=runs_root,
        sqlite_db=sqlite_db,
        workspace_root=workspace_root,
        run_id=run_id,
        session_id=session_id,
        window_id=str(args.window_id),
        window_date=str(args.window_date),
        paths=paths,
        retry_spike_status=str(args.retry_spike_status),
        approver=str(args.approver),
        notes=str(args.notes),
        allow_error_families=allow_families,
        strict=bool(args.strict),
    )
    failed_steps = [entry["name"] for entry in steps if int(entry.get("exit_code") or 0) != 0]
    signoff_payload = _load_signoff(paths.signoff) if paths.signoff.exists() else {}
    payload = {
        "schema_version": "protocol_enforce_window_capture_manifest.v1",
        "started_at_utc": started_at,
        "completed_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "window": {"id": str(args.window_id), "date": str(args.window_date)},
        "workspace_root": str(workspace_root).replace("\\", "/"),
        "runs_root": str(runs_root).replace("\\", "/"),
        "sqlite_db": str(sqlite_db).replace("\\", "/"),
        "run_id": run_id,
        "session_id": session_id,
        "strict": bool(args.strict),
        "steps": steps,
        "failed_steps": failed_steps,
        "artifacts": {
            "replay_campaign": str(paths.replay_campaign).replace("\\", "/"),
            "parity_campaign": str(paths.parity_campaign).replace("\\", "/"),
            "rollout_bundle": str(paths.rollout_bundle).replace("\\", "/"),
            "error_summary": str(paths.error_summary).replace("\\", "/"),
            "signoff": str(paths.signoff).replace("\\", "/"),
        },
        "signoff": {
            "gate_status": str(signoff_payload.get("gate_status") or ""),
            "all_gates_passed": bool(signoff_payload.get("all_gates_passed", False)),
        },
        "status": "PASS" if not failed_steps and bool(signoff_payload.get("all_gates_passed", False)) else "FAIL",
    }
    write_payload_with_diff_ledger(paths.manifest, payload)
    if bool(args.strict) and payload["status"] != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
