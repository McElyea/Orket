from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any
import uuid

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.core.cards_runtime_contract import ARTIFACT_EXECUTION_PROFILE, ODR_EXECUTION_PROFILE
from orket.runtime.defaults import DEFAULT_LOCAL_MODEL
from orket.runtime.execution_pipeline import ExecutionPipeline
from scripts.probes.probe_support import (
    applied_probe_env,
    is_environment_blocker,
    json_safe,
    now_utc_iso,
    protocol_events,
    read_json,
    run_summary,
    runtime_events,
    seed_runtime_settings_context,
    write_probe_runtime_root,
    write_report,
)

EPIC_ID = "probe-p04-odr-cards-integration"
DEFAULT_SESSION_ID = "probe-p04-odr-cards-integration"
DEFAULT_BUILD_ID = "build-probe-p04-odr-cards-integration"
DEFAULT_OUTPUT = "benchmarks/results/probes/p04_odr_cards_integration.json"


def _safe_token(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or "").strip()).strip("-") or "probe"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 1 probe P-04: live ODR/cards integration proof.")
    parser.add_argument("--workspace", default=".probe_workspace_p04")
    parser.add_argument("--session-id", default=DEFAULT_SESSION_ID)
    parser.add_argument("--build-id", default=DEFAULT_BUILD_ID)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--model", default=DEFAULT_LOCAL_MODEL)
    parser.add_argument("--provider", default="ollama")
    parser.add_argument("--ollama-host", default="")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _variant_token(root_workspace: Path) -> str:
    # Cards persistence is durable across runs, so default probe IDs must be unique
    # per invocation or reruns can reuse stale issue rows and cached odr_result data.
    return f"{_safe_token(root_workspace.name)}-{uuid.uuid4().hex[:10]}"


def _issue_id(*, variant_token: str, label: str) -> str:
    return f"{label}-{variant_token}-issue"


def _session_id(args: argparse.Namespace, *, variant_token: str, label: str) -> str:
    if str(args.session_id) != DEFAULT_SESSION_ID:
        return f"{args.session_id}-{label}"
    return f"{DEFAULT_SESSION_ID}-{variant_token}-{label}"


def _build_id(args: argparse.Namespace, *, variant_token: str, label: str) -> str:
    if str(args.build_id) != DEFAULT_BUILD_ID:
        return f"{args.build_id}-{label}"
    return f"{DEFAULT_BUILD_ID}-{variant_token}-{label}"


def _issue_payload(
    *,
    issue_id: str,
    execution_profile: str,
    artifact_path: str,
    odr_max_rounds: int | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "execution_profile": execution_profile,
        "artifact_contract": {
            "kind": "artifact",
            "primary_output": artifact_path,
            "required_write_paths": [artifact_path],
        },
    }
    if odr_max_rounds is not None:
        params["odr_max_rounds"] = int(odr_max_rounds)
    return {
        "id": issue_id,
        "summary": (
            f"Write {artifact_path} containing a Python function add(a, b) that returns a + b. "
            "Then call update_issue_status with status code_review in the same response."
        ),
        "seat": "coder",
        "priority": 1.0,
        "status": "ready",
        "depends_on": [],
        "params": params,
    }


def _event_counts(events: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in events:
        name = str(row.get("event") or "").strip()
        if not name:
            continue
        counts[name] = counts.get(name, 0) + 1
    return counts


def _variant_observation(workspace: Path, session_id: str) -> dict[str, Any]:
    summary = run_summary(workspace, session_id)
    runtime_rows = runtime_events(workspace, session_id)
    odr_artifact_path = str(summary.get("odr_artifact_path") or "").strip()
    odr_artifact_payload = {}
    if odr_artifact_path:
        artifact_file = workspace / odr_artifact_path
        if artifact_file.exists():
            payload = read_json(artifact_file)
            if isinstance(payload, dict):
                odr_artifact_payload = payload
    return {
        "run_summary": summary,
        "protocol_events": {
            "count": len(protocol_events(workspace, session_id)),
        },
        "runtime_events": {
            "count": len(runtime_rows),
            "event_counts": _event_counts(runtime_rows),
        },
        "odr_artifact_exists": bool(odr_artifact_payload),
        "odr_artifact": {
            "stop_reason": odr_artifact_payload.get("odr_stop_reason"),
            "odr_valid": odr_artifact_payload.get("odr_valid"),
            "history_round_count": len(odr_artifact_payload.get("history_rounds") or []),
            "accepted": odr_artifact_payload.get("accepted"),
        }
        if odr_artifact_payload
        else {},
    }


def _observed_result(non_odr: dict[str, Any], odr: dict[str, Any]) -> str:
    non_odr_summary = non_odr.get("run_summary") if isinstance(non_odr.get("run_summary"), dict) else {}
    odr_summary = odr.get("run_summary") if isinstance(odr.get("run_summary"), dict) else {}
    odr_artifact = odr.get("odr_artifact") if isinstance(odr.get("odr_artifact"), dict) else {}
    if bool(non_odr_summary.get("is_degraded")) or bool(odr_summary.get("is_degraded")):
        return "failure"
    if (
        non_odr_summary.get("odr_active") is False
        and str(non_odr_summary.get("status") or "").strip() == "done"
        and str(non_odr_summary.get("stop_reason") or "").strip() == "completed"
        and odr_summary.get("odr_active") is True
        and bool(odr_summary.get("odr_artifact_path"))
        and str(odr_summary.get("status") or "").strip() == "done"
        and str(odr_summary.get("stop_reason") or "").strip() == "completed"
        and odr_artifact.get("accepted") is True
    ):
        return "success"
    return "failure"


async def _run_probe(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(str(args.workspace)).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    non_odr_workspace = workspace / "non_odr"
    odr_workspace = workspace / "odr"
    variant_token = _variant_token(workspace)
    non_odr_issue_id = _issue_id(variant_token=variant_token, label="non-odr")
    odr_issue_id = _issue_id(variant_token=variant_token, label="odr")
    write_probe_runtime_root(
        non_odr_workspace,
        epic_id=EPIC_ID,
        environment_model=str(args.model),
        issues=[
            _issue_payload(
                issue_id=non_odr_issue_id,
                execution_profile=ARTIFACT_EXECUTION_PROFILE,
                artifact_path="agent_output/p04_non_odr.py",
            ),
        ],
        temperature=float(args.temperature),
        seed=int(args.seed),
        timeout=int(args.timeout),
    )
    write_probe_runtime_root(
        odr_workspace,
        epic_id=EPIC_ID,
        environment_model=str(args.model),
        issues=[
            _issue_payload(
                issue_id=odr_issue_id,
                execution_profile=ODR_EXECUTION_PROFILE,
                artifact_path="agent_output/p04_odr.py",
                odr_max_rounds=1,
            ),
        ],
        temperature=float(args.temperature),
        seed=int(args.seed),
        timeout=int(args.timeout),
    )

    with applied_probe_env(
        provider=str(args.provider),
        ollama_host=str(args.ollama_host or "").strip() or None,
        disable_sandbox=True,
    ):
        await seed_runtime_settings_context()
        non_odr_pipeline = ExecutionPipeline(
            workspace=non_odr_workspace,
            department="core",
            config_root=non_odr_workspace,
            run_ledger_repo=AsyncProtocolRunLedgerRepository(non_odr_workspace),
        )
        odr_pipeline = ExecutionPipeline(
            workspace=odr_workspace,
            department="core",
            config_root=odr_workspace,
            run_ledger_repo=AsyncProtocolRunLedgerRepository(odr_workspace),
        )
        non_odr_session_id = _session_id(args, variant_token=variant_token, label="non-odr")
        non_odr_build_id = _build_id(args, variant_token=variant_token, label="non-odr")
        odr_session_id = _session_id(args, variant_token=variant_token, label="odr")
        odr_build_id = _build_id(args, variant_token=variant_token, label="odr")
        non_odr_result = await non_odr_pipeline.run_card(
            non_odr_issue_id,
            session_id=non_odr_session_id,
            build_id=non_odr_build_id,
        )
        odr_result = await odr_pipeline.run_card(
            odr_issue_id,
            session_id=odr_session_id,
            build_id=odr_build_id,
        )

    non_odr_observation = _variant_observation(non_odr_workspace, non_odr_session_id)
    odr_observation = _variant_observation(odr_workspace, odr_session_id)
    observed_result = _observed_result(non_odr_observation, odr_observation)
    return {
        "schema_version": "phase1_probe.p04.v2",
        "recorded_at_utc": now_utc_iso(),
        "probe_id": "P-04",
        "probe_status": "observed",
        "proof_kind": "live",
        "observed_path": "primary",
        "observed_result": observed_result,
        "requested_provider": str(args.provider),
        "requested_model": str(args.model),
        "workspace": str(workspace),
        "variant_token": variant_token,
        "variants": {
            "non_odr": {
                "workspace": str(non_odr_workspace),
                "issue_id": non_odr_issue_id,
                "session_id": non_odr_session_id,
                "build_id": non_odr_build_id,
                "pipeline_result": json_safe(non_odr_result),
                **non_odr_observation,
            },
            "odr": {
                "workspace": str(odr_workspace),
                "issue_id": odr_issue_id,
                "session_id": odr_session_id,
                "build_id": odr_build_id,
                "pipeline_result": json_safe(odr_result),
                **odr_observation,
            },
        },
    }


def _blocked_payload(args: argparse.Namespace, error: Exception) -> dict[str, Any]:
    blocked = is_environment_blocker(error)
    return {
        "schema_version": "phase1_probe.p04.v2",
        "recorded_at_utc": now_utc_iso(),
        "probe_id": "P-04",
        "probe_status": "blocked",
        "proof_kind": "live",
        "observed_path": "blocked" if blocked else "primary",
        "observed_result": "environment blocker" if blocked else "failure",
        "requested_provider": str(args.provider),
        "requested_model": str(args.model),
        "workspace": str(Path(str(args.workspace)).resolve()),
        "error_type": type(error).__name__,
        "error": str(error),
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    output_path = Path(str(args.output)).resolve()
    try:
        payload = asyncio.run(_run_probe(args))
    except Exception as exc:  # noqa: BLE001
        payload = _blocked_payload(args, exc)

    persisted = write_report(output_path, payload)
    if args.json:
        print(json.dumps({**persisted, "output_path": str(output_path)}, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"probe_status={persisted.get('probe_status')}",
                    f"observed_result={persisted.get('observed_result')}",
                    f"output={output_path}",
                ]
            )
        )
    probe_status = str(persisted.get("probe_status") or "").strip().lower()
    observed_result = str(persisted.get("observed_result") or "").strip().lower()
    if probe_status != "observed":
        return 1
    return 0 if observed_result == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
