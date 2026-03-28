from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.adapters.storage.protocol_append_only_ledger import AppendOnlyRunLedger
from orket.orchestration.engine import OrchestrationEngine
from orket.runtime.defaults import DEFAULT_LOCAL_MODEL
from orket.runtime.live_acceptance_assets import write_core_acceptance_assets
from scripts.common.run_summary_support import load_validated_run_summary

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    import importlib.util

    helper_path = Path(__file__).resolve().parents[1] / "common" / "rerun_diff_ledger.py"
    spec = importlib.util.spec_from_file_location("rerun_diff_ledger", helper_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive fallback
        raise RuntimeError(f"E_DIFF_LEDGER_HELPER_LOAD_FAILED:{helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    write_payload_with_diff_ledger = module.write_payload_with_diff_ledger


def _now_utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record a live artifact-provenance proof artifact for truthful runtime Phase C packet-2.",
    )
    parser.add_argument("--model", default=os.getenv("ORKET_LIVE_MODEL", DEFAULT_LOCAL_MODEL))
    parser.add_argument("--provider", default=os.getenv("ORKET_LLM_PROVIDER", "ollama"))
    parser.add_argument(
        "--output",
        default="benchmarks/results/governance/truthful_runtime_artifact_provenance_live_proof.json",
    )
    parser.add_argument("--epic-id", default="truthful_runtime_artifact_provenance_live")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_bytes().decode("utf-8"))


def _run_roots(workspace: Path) -> list[Path]:
    runs_root = workspace / "runs"
    if not runs_root.exists():
        return []
    return sorted(path for path in runs_root.iterdir() if path.is_dir())


def _apply_env_overrides(overrides: dict[str, str]) -> dict[str, str | None]:
    previous: dict[str, str | None] = {}
    for key, value in overrides.items():
        previous[key] = os.environ.get(key)
        os.environ[key] = value
    return previous


def _restore_env(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
            continue
        os.environ[key] = value


def _proof_checks(
    *,
    run_summary: dict[str, Any],
    artifact_provenance: dict[str, Any],
    artifact_fact_events: list[dict[str, Any]],
    finalized_artifact_provenance: dict[str, Any] | None,
) -> dict[str, bool]:
    entries = list(artifact_provenance.get("artifacts") or [])
    paths = {str(entry.get("artifact_path") or "") for entry in entries}
    return {
        "status_done": str(run_summary.get("status") or "") == "done",
        "artifact_provenance_present": bool(artifact_provenance),
        "artifact_fact_recorded": bool(artifact_fact_events),
        "run_finalized_matches_summary": finalized_artifact_provenance == artifact_provenance,
        "requirements_recorded": "agent_output/requirements.txt" in paths,
        "design_recorded": "agent_output/design.txt" in paths,
        "main_recorded": "agent_output/main.py" in paths,
    }


def _build_success_payload(*, model: str, provider: str, epic_id: str, workspace: Path) -> dict[str, Any]:
    run_roots = _run_roots(workspace)
    if len(run_roots) != 1:
        raise ValueError(f"E_ARTIFACT_PROVENANCE_RUN_ROOTS_INVALID:{len(run_roots)}")
    run_root = run_roots[0]
    run_summary = load_validated_run_summary(run_root / "run_summary.json")
    run_id = str(run_summary.get("run_id") or "").strip()
    if not run_id:
        raise ValueError("E_ARTIFACT_PROVENANCE_RUN_ID_MISSING")
    artifact_provenance = dict(run_summary.get("truthful_runtime_artifact_provenance") or {})
    protocol_events = AppendOnlyRunLedger(run_root / "events.log").replay_events()
    artifact_fact_events = [
        row for row in protocol_events if str(row.get("kind") or "").strip() == "artifact_provenance_fact"
    ]
    finalized_event = next(
        (row for row in reversed(protocol_events) if str(row.get("kind") or "").strip() == "run_finalized"),
        None,
    )
    finalized_artifact_provenance = None
    if isinstance(finalized_event, dict):
        finalized_artifact_provenance = dict(
            (finalized_event.get("summary") or {}).get("truthful_runtime_artifact_provenance") or {}
        )
    checks = _proof_checks(
        run_summary=run_summary,
        artifact_provenance=artifact_provenance,
        artifact_fact_events=artifact_fact_events,
        finalized_artifact_provenance=finalized_artifact_provenance,
    )
    return {
        "schema_version": "truthful_runtime_artifact_provenance_live_proof.v1",
        "recorded_at_utc": _now_utc_iso(),
        "proof_kind": "live",
        "proof_target": "truthful_runtime_phase_c_packet2_artifact_provenance",
        "observed_path": "primary",
        "observed_result": "success" if all(checks.values()) else "failure",
        "provider_requested": provider,
        "model_requested": model,
        "epic_id": epic_id,
        "notes": [
            "This is a provider-backed live acceptance run.",
            "Artifact provenance is harvested from successful protocol write receipts when present.",
            "When protocol receipts are absent, the recorder falls back to correlated tool_call_start/tool_call_result evidence.",
        ],
        "run": {
            "run_id": run_id,
            "status": run_summary.get("status"),
            "truthful_runtime_artifact_provenance": artifact_provenance,
        },
        "evidence": {
            "artifact_provenance_fact_events": artifact_fact_events,
            "run_finalized_truthful_runtime_artifact_provenance": finalized_artifact_provenance,
            "protocol_event_count": len(protocol_events),
        },
        "checks": checks,
    }


def _error_payload(*, model: str, provider: str, epic_id: str, error: Exception) -> dict[str, Any]:
    message = str(error).strip()
    lower_message = message.lower()
    environment_blocker = any(
        token in lower_message
        for token in ("ollama", "connection refused", "not found", "model", "provider", "timed out")
    )
    return {
        "schema_version": "truthful_runtime_artifact_provenance_live_proof.v1",
        "recorded_at_utc": _now_utc_iso(),
        "proof_kind": "live",
        "proof_target": "truthful_runtime_phase_c_packet2_artifact_provenance",
        "observed_path": "blocked" if environment_blocker else "primary",
        "observed_result": "environment blocker" if environment_blocker else "failure",
        "provider_requested": provider,
        "model_requested": model,
        "epic_id": epic_id,
        "error_type": type(error).__name__,
        "error": message,
    }


async def _execute_live_proof(
    *,
    engine: OrchestrationEngine,
    workspace: Path,
    model: str,
    provider: str,
    epic_id: str,
) -> dict[str, Any]:
    await engine.run_card(epic_id)
    return _build_success_payload(
        model=model,
        provider=provider,
        epic_id=epic_id,
        workspace=workspace,
    )


def record_truthful_runtime_artifact_provenance_live_proof(
    *,
    model: str,
    provider: str,
    epic_id: str,
) -> dict[str, Any]:
    overrides = _apply_env_overrides(
        {
            "ORKET_RUN_LEDGER_MODE": "protocol",
            "ORKET_LLM_PROVIDER": provider,
            "ORKET_DISABLE_SANDBOX": "1",
        }
    )
    try:
        with tempfile.TemporaryDirectory(prefix="orket-artifact-provenance-live-") as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "agent_output").mkdir()
            (workspace / "verification").mkdir()
            db_path = str(root / "artifact_provenance_live.db")
            write_core_acceptance_assets(root, epic_id=epic_id, environment_model=model)
            engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
            return asyncio.run(
                _execute_live_proof(
                    engine=engine,
                    workspace=workspace,
                    model=model,
                    provider=provider,
                    epic_id=epic_id,
                )
            )
    finally:
        _restore_env(overrides)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    model = str(args.model or "").strip() or DEFAULT_LOCAL_MODEL
    provider = str(args.provider or "").strip() or "ollama"
    epic_id = str(args.epic_id or "").strip() or "truthful_runtime_artifact_provenance_live"
    output_path = Path(str(args.output)).resolve()

    try:
        payload = record_truthful_runtime_artifact_provenance_live_proof(
            model=model,
            provider=provider,
            epic_id=epic_id,
        )
    except Exception as exc:  # pragma: no cover - top-level CLI failure boundary
        payload = _error_payload(model=model, provider=provider, epic_id=epic_id, error=exc)

    persisted = write_payload_with_diff_ledger(output_path, payload)
    if args.json:
        print(json.dumps({**persisted, "out_path": str(output_path)}, indent=2, ensure_ascii=True, sort_keys=True))
    else:
        print(
            " ".join(
                [
                    f"result={persisted.get('observed_result')}",
                    f"path={persisted.get('observed_path')}",
                    f"output={output_path}",
                ]
            )
        )
    return 0 if str(persisted.get("observed_result") or "") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
