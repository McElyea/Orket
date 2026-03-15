from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse
from orket.adapters.storage.protocol_append_only_ledger import AppendOnlyRunLedger
from orket.orchestration.engine import OrchestrationEngine
from orket.runtime.live_acceptance_assets import write_core_acceptance_assets
from orket.runtime.run_summary import PACKET1_MISSING_TOKEN

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
        description="Record a live repaired-path packet-2 repair-ledger proof artifact.",
    )
    parser.add_argument("--model", default=os.getenv("ORKET_LIVE_MODEL", "qwen2.5-coder:7b"))
    parser.add_argument("--provider", default=os.getenv("ORKET_LLM_PROVIDER", "ollama"))
    parser.add_argument(
        "--output",
        default="benchmarks/results/governance/truthful_runtime_packet2_repair_live_proof.json",
    )
    parser.add_argument("--epic-id", default="truthful_runtime_packet2_repair_live")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_bytes().decode("utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_bytes().decode("utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


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


def _repair_injector(
    original_complete: Callable[..., Awaitable[ModelResponse]],
    applied_flag: dict[str, bool],
) -> Callable[..., Awaitable[ModelResponse]]:
    async def _corrupt_first_response(self, messages, runtime_context=None):
        response = await original_complete(self, messages, runtime_context=runtime_context)
        context = dict(runtime_context or {})
        role_tokens = {
            str(value).strip().lower()
            for value in (context.get("roles") or [context.get("role")])
            if str(value).strip()
        }
        if "integrity_guard" not in role_tokens or applied_flag["value"]:
            return response
        applied_flag["value"] = True
        raw = dict(getattr(response, "raw", {}) or {})
        return ModelResponse(content=f"Done.\n{response.content}", raw=raw)

    return _corrupt_first_response


def _filtered_corrective_events(*, workspace: Path, run_id: str) -> list[dict[str, Any]]:
    rows = _read_jsonl(workspace / "orket.log")
    return [
        row
        for row in rows
        if str(row.get("event") or "").strip() == "turn_corrective_reprompt"
        and str(((row.get("data") or {}).get("session_id") or "")).strip() == run_id
    ]


def _protocol_events(run_root: Path) -> list[dict[str, Any]]:
    return AppendOnlyRunLedger(run_root / "events.log").replay_events()


def _observed_path(packet1: dict[str, Any]) -> str:
    provenance = dict(packet1.get("provenance") or {})
    if bool(provenance.get("fallback_occurred")) or str(provenance.get("execution_profile") or "") == "fallback":
        return "fallback"
    if str((packet1.get("classification") or {}).get("truth_classification") or "") == "degraded":
        return "degraded"
    return "primary"


def _proof_checks(
    *,
    run_summary: dict[str, Any],
    packet1: dict[str, Any],
    packet2: dict[str, Any],
    corrective_events: list[dict[str, Any]],
    packet2_fact_events: list[dict[str, Any]],
    finalized_packet2: dict[str, Any] | None,
    repair_injection_applied: bool,
) -> dict[str, bool]:
    repair_ledger = dict(packet2.get("repair_ledger") or {})
    entries = list(repair_ledger.get("entries") or [])
    return {
        "status_done": str(run_summary.get("status") or "") == "done",
        "packet1_primary_output_main_py": str((packet1.get("provenance") or {}).get("primary_output_id") or "")
        == "agent_output/main.py",
        "classification_repaired": str((packet1.get("classification") or {}).get("truth_classification") or "")
        == "repaired",
        "silent_repaired_success_present": "silent_repaired_success"
        in list((packet1.get("defects") or {}).get("defect_families") or []),
        "repair_occurred": bool((packet1.get("provenance") or {}).get("repair_occurred")),
        "intended_model_not_missing": str((packet1.get("provenance") or {}).get("intended_model") or "")
        != PACKET1_MISSING_TOKEN,
        "intended_profile_not_missing": str((packet1.get("provenance") or {}).get("intended_profile") or "")
        != PACKET1_MISSING_TOKEN,
        "packet2_repair_ledger_present": bool(packet2),
        "packet2_entries_present": len(entries) >= 1,
        "packet2_disposition_accepted_with_repair": str(repair_ledger.get("final_disposition") or "")
        == "accepted_with_repair",
        "corrective_reprompt_logged": bool(corrective_events),
        "packet2_fact_recorded": bool(packet2_fact_events),
        "run_finalized_packet2_matches_summary": finalized_packet2 == packet2,
        "repair_injection_applied": bool(repair_injection_applied),
    }


def _build_success_payload(
    *,
    model: str,
    provider: str,
    epic_id: str,
    workspace: Path,
    repair_injection_applied: bool,
) -> dict[str, Any]:
    run_roots = _run_roots(workspace)
    if len(run_roots) != 1:
        raise ValueError(f"E_PACKET2_REPAIR_RUN_ROOTS_INVALID:{len(run_roots)}")
    run_root = run_roots[0]
    run_summary = _read_json(run_root / "run_summary.json")
    run_id = str(run_summary.get("run_id") or "").strip()
    if not run_id:
        raise ValueError("E_PACKET2_REPAIR_RUN_ID_MISSING")
    packet1 = dict(run_summary.get("truthful_runtime_packet1") or {})
    packet2 = dict(run_summary.get("truthful_runtime_packet2") or {})
    protocol_events = _protocol_events(run_root)
    corrective_events = _filtered_corrective_events(workspace=workspace, run_id=run_id)
    packet2_fact_events = [row for row in protocol_events if str(row.get("kind") or "").strip() == "packet2_fact"]
    finalized_event = next(
        (row for row in reversed(protocol_events) if str(row.get("kind") or "").strip() == "run_finalized"),
        None,
    )
    finalized_packet2 = None
    if isinstance(finalized_event, dict):
        finalized_packet2 = dict((finalized_event.get("summary") or {}).get("truthful_runtime_packet2") or {})
    checks = _proof_checks(
        run_summary=run_summary,
        packet1=packet1,
        packet2=packet2,
        corrective_events=corrective_events,
        packet2_fact_events=packet2_fact_events,
        finalized_packet2=finalized_packet2,
        repair_injection_applied=repair_injection_applied,
    )
    observed_result = "success" if all(checks.values()) else "failure"
    return {
        "schema_version": "truthful_runtime_packet2_repair_live_proof.v1",
        "recorded_at_utc": _now_utc_iso(),
        "proof_kind": "live",
        "proof_target": "truthful_runtime_phase_c_packet2_repair_ledger",
        "observed_path": _observed_path(packet1),
        "observed_result": observed_result,
        "provider_requested": provider,
        "model_requested": model,
        "epic_id": epic_id,
        "repair_trigger_mode": "injected_integrity_guard_prefix",
        "notes": [
            "This is a provider-backed live run.",
            "The first integrity_guard response is intentionally corrupted locally to force the repair path.",
        ],
        "run": {
            "run_id": run_id,
            "status": run_summary.get("status"),
            "truthful_runtime_packet1": packet1,
            "truthful_runtime_packet2": packet2,
        },
        "evidence": {
            "corrective_reprompt_events": corrective_events,
            "packet2_fact_events": packet2_fact_events,
            "run_finalized_truthful_runtime_packet2": finalized_packet2,
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
        "schema_version": "truthful_runtime_packet2_repair_live_proof.v1",
        "recorded_at_utc": _now_utc_iso(),
        "proof_kind": "live",
        "proof_target": "truthful_runtime_phase_c_packet2_repair_ledger",
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
    repair_injection_applied: dict[str, bool],
) -> dict[str, Any]:
    await engine.run_card(epic_id)
    return _build_success_payload(
        model=model,
        provider=provider,
        epic_id=epic_id,
        workspace=workspace,
        repair_injection_applied=repair_injection_applied["value"],
    )


def record_truthful_runtime_packet2_repair_live_proof(
    *,
    model: str,
    provider: str,
    epic_id: str,
) -> dict[str, Any]:
    overrides = _apply_env_overrides(
        {
            "ORKET_RUN_LEDGER_MODE": "protocol",
            "ORKET_LLM_PROVIDER": provider,
        }
    )
    original_complete = LocalModelProvider.complete
    repair_injection_applied = {"value": False}
    LocalModelProvider.complete = _repair_injector(original_complete, repair_injection_applied)
    try:
        with tempfile.TemporaryDirectory(prefix="orket-packet2-repair-live-") as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "agent_output").mkdir()
            (workspace / "verification").mkdir()
            db_path = str(root / "packet2_repair_live.db")
            write_core_acceptance_assets(root, epic_id=epic_id, environment_model=model)
            engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
            return asyncio.run(
                _execute_live_proof(
                    engine=engine,
                    workspace=workspace,
                    model=model,
                    provider=provider,
                    epic_id=epic_id,
                    repair_injection_applied=repair_injection_applied,
                )
            )
    finally:
        LocalModelProvider.complete = original_complete
        _restore_env(overrides)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    model = str(args.model or "").strip() or "qwen2.5-coder:7b"
    provider = str(args.provider or "").strip() or "ollama"
    epic_id = str(args.epic_id or "").strip() or "truthful_runtime_packet2_repair_live"
    output_path = Path(str(args.output)).resolve()

    try:
        payload = record_truthful_runtime_packet2_repair_live_proof(
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
