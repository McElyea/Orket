#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.core.cards_runtime_contract import ARTIFACT_EXECUTION_PROFILE
from orket.runtime.defaults import DEFAULT_LOCAL_MODEL
from orket.runtime.execution_pipeline import ExecutionPipeline
from scripts.probes.probe_support import (
    applied_probe_env,
    is_environment_blocker,
    json_safe,
    now_utc_iso,
    protocol_events,
    run_summary,
    runtime_events,
    write_probe_runtime_root,
    write_report,
)
from scripts.workloads.workload_support import (
    artifact_inventory,
    display_path,
    load_json_object,
    load_python_symbols,
    run_strict_json_model,
    validate_json_contract,
    write_json,
)

DEFAULT_OUTPUT = "benchmarks/results/workloads/generate_and_verify.json"
DEFAULT_FIXTURE = "scripts/workloads/fixtures/generate_and_verify_v1/function_spec.json"
DEFAULT_WORKSPACE = "workspace/default"
DEFAULT_SESSION_ID = "workload-s05-generate-and-verify"
DEFAULT_BUILD_ID = "build-workload-s05-generate-and-verify"
EPIC_ID = "workload-s05-generate-and-verify"
ISSUE_ID = "S05-GEN-VERIFY"


class _VerifierContract(BaseModel):
    verdict: str
    confidence: float
    reasons: list[str] = Field(default_factory=list)
    next_step: str = ""


def _safe_token(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or "").strip()).strip("-") or "probe"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 3 workload S-05: cards-backed generate-and-verify probe.")
    parser.add_argument("--workspace", default=DEFAULT_WORKSPACE)
    parser.add_argument("--fixture", default=DEFAULT_FIXTURE)
    parser.add_argument("--model", default=DEFAULT_LOCAL_MODEL)
    parser.add_argument("--provider", default="ollama")
    parser.add_argument("--ollama-host", default="")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--session-id", default=DEFAULT_SESSION_ID)
    parser.add_argument("--build-id", default=DEFAULT_BUILD_ID)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _effective_session_id(args: argparse.Namespace, workspace: Path) -> str:
    if str(args.session_id) != DEFAULT_SESSION_ID:
        return str(args.session_id)
    return f"{DEFAULT_SESSION_ID}-{_safe_token(workspace.name)}"


def _effective_build_id(args: argparse.Namespace, workspace: Path) -> str:
    if str(args.build_id) != DEFAULT_BUILD_ID:
        return str(args.build_id)
    return f"{DEFAULT_BUILD_ID}-{_safe_token(workspace.name)}"


def _effective_issue_id(workspace: Path) -> str:
    return f"{ISSUE_ID}-{_safe_token(workspace.name)}"


def _issue_payload(spec: dict[str, Any], issue_id: str) -> dict[str, Any]:
    artifact_path = str(spec.get("artifact_path") or "").strip()
    return {
        "id": issue_id,
        "summary": str(spec.get("issue_summary") or "").strip(),
        "seat": "coder",
        "priority": 1.0,
        "status": "ready",
        "depends_on": [],
        "params": {
            "execution_profile": ARTIFACT_EXECUTION_PROFILE,
            "artifact_contract": {
                "kind": "artifact",
                "primary_output": artifact_path,
                "required_write_paths": [artifact_path],
            },
        },
    }


def _execute_test_cases(*, module_path: Path, function_name: str, test_cases: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "artifact_exists": module_path.exists(),
        "syntax_valid": False,
        "callable_loaded": False,
        "function_name": function_name,
        "cases": [],
        "passed": 0,
        "failed": 0,
    }
    if not module_path.exists():
        result["error"] = "artifact_missing"
        return result
    try:
        symbols = load_python_symbols(module_path)
        result["syntax_valid"] = True
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"syntax_error:{type(exc).__name__}:{exc}"
        return result
    function = symbols.get(function_name)
    if not callable(function):
        result["error"] = "callable_missing"
        return result
    result["callable_loaded"] = True
    for case in test_cases:
        args = list(case.get("args") or [])
        expected = case.get("expected")
        row = {"name": str(case.get("name") or ""), "args": args, "expected": expected}
        try:
            actual = function(*args)
            row["actual"] = actual
            row["passed"] = actual == expected
        except Exception as exc:  # noqa: BLE001
            row["error"] = f"{type(exc).__name__}:{exc}"
            row["passed"] = False
        if row["passed"]:
            result["passed"] += 1
        else:
            result["failed"] += 1
        result["cases"].append(row)
    result["all_passed"] = result["failed"] == 0 and result["callable_loaded"]
    return result


def _build_verifier_messages(*, spec: dict[str, Any], source_text: str, verification: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Return exactly one JSON object with keys verdict, confidence, reasons, next_step. "
                "Use verdict in {pass, fail, uncertain}. confidence must be a number from 0.0 to 1.0. "
                "Keep reasons short and concrete. Do not use markdown fences."
            ),
        },
        {
            "role": "user",
            "content": (
                "Assess whether the generated function satisfies the spec.\n"
                f"Signature: {spec.get('signature')}\n"
                f"Docstring: {spec.get('docstring')}\n"
                f"Generated source:\n{source_text}\n\n"
                f"Deterministic verification:\n{json.dumps(verification, sort_keys=True)}"
            ),
        },
    ]


def _observed_result(*, run_status: str, verification: dict[str, Any], verifier_contract_valid: bool) -> str:
    if run_status != "done":
        return "failure"
    if bool(verification.get("all_passed")) and verifier_contract_valid:
        return "success"
    if bool(verification.get("artifact_exists")):
        return "partial success"
    return "failure"


async def _run_probe(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(str(args.workspace)).resolve()
    fixture_path = Path(str(args.fixture)).resolve()
    if not fixture_path.is_file():
        raise FileNotFoundError(f"fixture_not_found:{fixture_path}")
    spec = load_json_object(fixture_path)
    artifact_path = str(spec.get("artifact_path") or "").strip()
    if not artifact_path:
        raise ValueError("fixture_missing_artifact_path")

    session_id = _effective_session_id(args, workspace)
    build_id = _effective_build_id(args, workspace)
    issue_id = _effective_issue_id(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    write_probe_runtime_root(
        workspace,
        epic_id=EPIC_ID,
        environment_model=str(args.model),
        issues=[_issue_payload(spec, issue_id)],
        temperature=float(args.temperature),
        seed=int(args.seed),
        timeout=int(args.timeout),
    )

    with applied_probe_env(
        provider=str(args.provider),
        ollama_host=str(args.ollama_host or "").strip() or None,
        disable_sandbox=True,
    ):
        pipeline = ExecutionPipeline(
            workspace=workspace,
            department="core",
            config_root=workspace,
            run_ledger_repo=AsyncProtocolRunLedgerRepository(workspace),
        )
        pipeline_result = await pipeline.run_card(issue_id, session_id=session_id, build_id=build_id)

    summary = run_summary(workspace, session_id)
    generated_file = workspace / artifact_path
    source_text = generated_file.read_text(encoding="utf-8") if generated_file.exists() else ""
    verification = _execute_test_cases(
        module_path=generated_file,
        function_name=str(spec.get("function_name") or ""),
        test_cases=[dict(row) for row in list(spec.get("test_cases") or []) if isinstance(row, dict)],
    )
    verifier_text, verifier_raw = await run_strict_json_model(
        model=str(args.model),
        provider=str(args.provider),
        ollama_host=str(args.ollama_host),
        temperature=float(args.temperature),
        seed=int(args.seed),
        timeout=int(args.timeout),
        messages=_build_verifier_messages(spec=spec, source_text=source_text, verification=verification),
        runtime_context={"workload_id": "S-05", "fixture_id": str(spec.get("fixture_id") or "")},
    )
    verifier_payload, response_json_found, verifier_contract_valid, advisory_errors = validate_json_contract(
        text=verifier_text,
        model_cls=_VerifierContract,
    )

    artifact_dir = workspace / "workloads" / "s05_generate_and_verify" / build_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_json(artifact_dir / "function_spec.json", spec)
    write_json(artifact_dir / "cards_run_summary.json", summary)
    write_json(artifact_dir / "cards_pipeline_result.json", json_safe(pipeline_result))
    write_json(artifact_dir / "deterministic_verification.json", verification)
    write_json(artifact_dir / "model_verifier.json", verifier_payload)
    write_json(artifact_dir / "model_verifier_raw.json", verifier_raw)
    if source_text:
        (artifact_dir / "generated_source.py").write_text(source_text, encoding="utf-8")
    (artifact_dir / "model_verifier_response.txt").write_text(verifier_text, encoding="utf-8")

    observed_result = _observed_result(
        run_status=str(summary.get("status") or ""),
        verification=verification,
        verifier_contract_valid=verifier_contract_valid,
    )
    return {
        "schema_version": "workloads.s05_generate_and_verify.v1",
        "recorded_at_utc": now_utc_iso(),
        "workload_id": "S-05",
        "probe_status": "observed",
        "proof_kind": "live",
        "observed_path": "primary",
        "observed_result": observed_result,
        "requested_provider": str(args.provider),
        "requested_model": str(args.model),
        "workspace": str(workspace),
        "session_id": session_id,
        "build_id": build_id,
        "fixture": {
            "fixture_id": str(spec.get("fixture_id") or ""),
            "fixture_path": display_path(fixture_path),
            "artifact_path": artifact_path,
            "signature": str(spec.get("signature") or ""),
        },
        "run_summary": summary,
        "protocol_events": {"count": len(protocol_events(workspace, session_id))},
        "runtime_events": {"count": len(runtime_events(workspace, session_id))},
        "deterministic_verification": verification,
        "model_verifier": {
            "response_json_found": response_json_found,
            "contract_valid": verifier_contract_valid,
            "advisory_errors": advisory_errors,
            "payload": verifier_payload,
        },
        "artifact_bundle": {
            "path": artifact_dir.as_posix(),
            "files": artifact_inventory(artifact_dir),
        },
    }


def _blocked_payload(args: argparse.Namespace, error: Exception) -> dict[str, Any]:
    blocked = is_environment_blocker(error)
    return {
        "schema_version": "workloads.s05_generate_and_verify.v1",
        "recorded_at_utc": now_utc_iso(),
        "workload_id": "S-05",
        "probe_status": "blocked",
        "proof_kind": "live",
        "observed_path": "blocked" if blocked else "primary",
        "observed_result": "environment blocker" if blocked else "failure",
        "requested_provider": str(args.provider),
        "requested_model": str(args.model),
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
        verification = persisted.get("deterministic_verification") if isinstance(persisted.get("deterministic_verification"), dict) else {}
        print(
            " ".join(
                [
                    f"probe_status={persisted.get('probe_status')}",
                    f"observed_result={persisted.get('observed_result')}",
                    f"tests_passed={verification.get('passed', '')}",
                    f"tests_failed={verification.get('failed', '')}",
                    f"output={output_path}",
                ]
            )
        )
    return 0 if str(persisted.get("probe_status") or "") == "observed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
