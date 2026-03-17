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
from orket.runtime.live_acceptance_assets import write_core_acceptance_assets

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
        description="Record a live packet-1 proof artifact under the corrected primary-boundary contract.",
    )
    parser.add_argument("--model", default=os.getenv("ORKET_LIVE_MODEL", "qwen2.5-coder:7b"))
    parser.add_argument("--provider", default=os.getenv("ORKET_LLM_PROVIDER", "ollama"))
    parser.add_argument(
        "--output",
        default="benchmarks/results/governance/truthful_runtime_packet1_live_proof.json",
    )
    parser.add_argument("--epic-id", default="truthful_runtime_packet1_live")
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


def _protocol_events(run_root: Path) -> list[dict[str, Any]]:
    return AppendOnlyRunLedger(run_root / "events.log").replay_events()


async def _run_command(*args: str) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return process.returncode, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")


async def _ensure_ollama_alias(source_model: str, alias_model: str) -> None:
    show_code, _, _ = await _run_command("ollama", "show", alias_model)
    if show_code == 0:
        return
    copy_code, _, copy_stderr = await _run_command("ollama", "cp", source_model, alias_model)
    if copy_code != 0:
        raise AssertionError(f"failed to create ollama alias {alias_model}: {copy_stderr.strip()}")


async def _remove_ollama_alias(alias_model: str) -> None:
    await _run_command("ollama", "rm", alias_model)


def _proof_checks(
    *,
    run_summary: dict[str, Any],
    packet1: dict[str, Any],
    artifact_provenance: dict[str, Any],
    finalized_packet1: dict[str, Any] | None,
) -> dict[str, bool]:
    artifact_entries = list(artifact_provenance.get("artifacts") or [])
    packet1_provenance = dict(packet1.get("provenance") or {})
    return {
        "status_done": str(run_summary.get("status") or "") == "done",
        "packet1_present": bool(packet1),
        "primary_output_main_py": str(packet1_provenance.get("primary_output_id") or "") == "agent_output/main.py",
        "classification_degraded": str((packet1.get("classification") or {}).get("truth_classification") or "")
        == "degraded",
        "degraded_success_defect_present": "silent_degraded_success"
        in list((packet1.get("defects") or {}).get("defect_families") or []),
        "packet1_non_conformant": str((packet1.get("packet1_conformance") or {}).get("status") or "") == "non_conformant",
        "artifact_provenance_present": bool(artifact_provenance),
        "main_recorded_in_provenance": any(
            str(entry.get("artifact_path") or "") == "agent_output/main.py" for entry in artifact_entries
        ),
        "run_finalized_packet1_matches_summary": finalized_packet1 == packet1,
    }


def _build_success_payload(
    *,
    model: str,
    provider: str,
    epic_id: str,
    workspace: Path,
) -> dict[str, Any]:
    run_roots = _run_roots(workspace)
    if len(run_roots) != 1:
        raise ValueError(f"E_PACKET1_RUN_ROOTS_INVALID:{len(run_roots)}")
    run_root = run_roots[0]
    run_summary = _read_json(run_root / "run_summary.json")
    run_id = str(run_summary.get("run_id") or "").strip()
    if not run_id:
        raise ValueError("E_PACKET1_RUN_ID_MISSING")
    packet1 = dict(run_summary.get("truthful_runtime_packet1") or {})
    artifact_provenance = dict(run_summary.get("truthful_runtime_artifact_provenance") or {})
    runtime_verification = _read_json(workspace / "agent_output" / "verification" / "runtime_verification.json")
    protocol_events = _protocol_events(run_root)
    finalized_event = next(
        (row for row in reversed(protocol_events) if str(row.get("kind") or "").strip() == "run_finalized"),
        None,
    )
    finalized_packet1 = None
    if isinstance(finalized_event, dict):
        finalized_packet1 = dict((finalized_event.get("summary") or {}).get("truthful_runtime_packet1") or {})
    checks = _proof_checks(
        run_summary=run_summary,
        packet1=packet1,
        artifact_provenance=artifact_provenance,
        finalized_packet1=finalized_packet1,
    )
    observed_result = "success" if all(checks.values()) else "failure"
    return {
        "schema_version": "truthful_runtime_packet1_live_proof.v2",
        "recorded_at_utc": _now_utc_iso(),
        "proof_kind": "live",
        "proof_target": "truthful_runtime_phase_c_packet1_boundary_cleanup",
        "observed_path": "fallback",
        "observed_result": observed_result,
        "provider_requested": provider,
        "model_requested": model,
        "epic_id": epic_id,
        "fallback_profile_id": "ollama.qwen.chatml.v1",
        "notes": [
            "This is a provider-backed live fallback-profile run under the corrected packet-1 primary-boundary contract.",
            "The live proof uses an explicit local-prompt fallback-profile path because the full direct-success acceptance path is currently volatile on provider-backed runs.",
            "Packet-1 proof targets runtime truth surfaces rather than semantic artifact quality.",
        ],
        "run": {
            "run_id": run_id,
            "status": run_summary.get("status"),
            "truthful_runtime_packet1": packet1,
            "truthful_runtime_artifact_provenance": artifact_provenance,
            "runtime_verification": runtime_verification,
        },
        "evidence": {
            "run_finalized_truthful_runtime_packet1": finalized_packet1,
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
        "schema_version": "truthful_runtime_packet1_live_proof.v2",
        "recorded_at_utc": _now_utc_iso(),
        "proof_kind": "live",
        "proof_target": "truthful_runtime_phase_c_packet1_boundary_cleanup",
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


def record_truthful_runtime_packet1_live_proof(
    *,
    model: str,
    provider: str,
    epic_id: str,
) -> dict[str, Any]:
    alias_model = "packet1-boundary-proof:7b"
    overrides = _apply_env_overrides(
        {
            "ORKET_RUN_LEDGER_MODE": "protocol",
            "ORKET_LLM_PROVIDER": provider,
            "ORKET_DISABLE_SANDBOX": "1",
            "ORKET_LOCAL_PROMPTING_MODE": "enforce",
            "ORKET_LOCAL_PROMPTING_ALLOW_FALLBACK": "true",
            "ORKET_LOCAL_PROMPTING_FALLBACK_PROFILE_ID": "ollama.qwen.chatml.v1",
        }
    )
    try:
        asyncio.run(_ensure_ollama_alias(model, alias_model))
        with tempfile.TemporaryDirectory(prefix="orket-packet1-live-") as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "agent_output").mkdir()
            (workspace / "verification").mkdir()
            db_path = str(root / "packet1_live.db")
            write_core_acceptance_assets(root, epic_id=epic_id, environment_model=alias_model)
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
        asyncio.run(_remove_ollama_alias(alias_model))
        _restore_env(overrides)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    model = str(args.model or "").strip() or "qwen2.5-coder:7b"
    provider = str(args.provider or "").strip() or "ollama"
    epic_id = str(args.epic_id or "").strip() or "truthful_runtime_packet1_live"
    output_path = Path(str(args.output)).resolve()

    try:
        payload = record_truthful_runtime_packet1_live_proof(
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
