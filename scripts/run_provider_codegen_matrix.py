from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

# This script is intended to live under repo_root/scripts/
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.runtime.execution_pipeline import ExecutionPipeline
from scripts.probes.probe_support import (
    applied_probe_env,
    is_environment_blocker,
    now_utc_iso,
    observability_inventory,
    protocol_events,
    run_summary,
    runtime_events,
    write_json,
    write_probe_runtime_root,
)

EPIC_ID = "probe-req-to-code-chain"
TEAM_NAME = "requirements_to_code_chain"
ENV_NAME = "standard"
DEFAULT_REQUIREMENTS = """Build a tiny Python command line tool for renaming files from metadata.

Bad brief on purpose:
- it should be simple but production ready
- rename files using metadata but don't change anything dangerous
- maybe support dry run or maybe not, probably yes
- Windows first but should be cross platform if easy
- use JSON or YAML or whatever makes sense
- should be very fast even on huge folders
- preserve originals somehow
- output should be clear
- I might want recursive mode later
- no external deps unless really needed
- add tests if that makes sense
- keep it small
"""


@dataclass(frozen=True)
class ProviderRun:
    label: str
    provider: str
    model: str
    workspace: Path
    preflight_output: Path
    baseline_output: Path
    chain_output: Path


@dataclass(frozen=True)
class PairSpec:
    name: str
    ollama_model: str
    lmstudio_model: str


def _safe_token(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or "").strip()).strip("-") or "probe"


def _write_role(root: Path, *, role_name: str, description: str, tools: list[str]) -> None:
    payload = {
        "name": role_name,
        "description": description,
        "tools": tools,
        "metadata": {"id": f"role.{role_name}"},
    }
    write_json(root / "model" / "core" / "roles" / f"{role_name}.json", payload)


def _write_team(root: Path) -> None:
    payload = {
        "name": TEAM_NAME,
        "description": "Probe-only requirements-to-code chain.",
        "seats": {
            "requirements_analyst": {"name": "Requirements Analyst", "roles": ["requirements_analyst"]},
            "coder": {"name": "Coder", "roles": ["coder"]},
            "code_reviewer": {"name": "Code Reviewer", "roles": ["code_reviewer"]},
            "integrity_guard": {"name": "Integrity Guard", "roles": ["integrity_guard"]},
        },
    }
    write_json(root / "model" / "core" / "teams" / f"{TEAM_NAME}.json", payload)


def _issue_payloads() -> list[dict[str, Any]]:
    bad_req_path = "input/bad_requirements.txt"
    req_doc = "agent_output/requirements.md"
    test_doc = "agent_output/acceptance_tests.md"
    code_path = "agent_output/main.py"
    return [
        {
            "id": "REQ-1",
            "summary": (
                f"Read {bad_req_path}. It is intentionally ambiguous and partially contradictory. "
                f"Write {req_doc} with these exact sections: Summary, Must, Assumptions, Open Questions, Non-Goals. "
                "Resolve obvious wording problems, but do not invent missing facts as settled requirements. "
                "Call update_issue_status with status code_review in the same response."
            ),
            "seat": "requirements_analyst",
            "priority": 1.0,
            "status": "ready",
            "depends_on": [],
            "params": {
                "artifact_contract": {
                    "kind": "artifact",
                    "primary_output": req_doc,
                    "required_read_paths": [bad_req_path],
                    "required_write_paths": [req_doc],
                }
            },
        },
        {
            "id": "REQ-2",
            "summary": (
                f"Read {req_doc}. Write {test_doc} containing a small acceptance test checklist with: Happy Path, Error Handling, Safety Checks, and Deferred Cases. "
                "Keep it short and concrete. Call update_issue_status with status code_review in the same response."
            ),
            "seat": "requirements_analyst",
            "priority": 2.0,
            "status": "ready",
            "depends_on": ["REQ-1"],
            "params": {
                "artifact_contract": {
                    "kind": "artifact",
                    "primary_output": test_doc,
                    "required_read_paths": [req_doc],
                    "required_write_paths": [test_doc],
                }
            },
        },
        {
            "id": "COD-1",
            "summary": (
                f"Read {req_doc} and {test_doc}. Implement {code_path} as a small Python CLI. "
                "When the bad brief conflicts with the refined requirements, follow the refined requirements. "
                "Keep the implementation small, local, and dependency-light. "
                "Call update_issue_status with status code_review in the same response."
            ),
            "seat": "coder",
            "priority": 3.0,
            "status": "ready",
            "depends_on": ["REQ-1", "REQ-2"],
            "params": {
                "artifact_contract": {
                    "kind": "artifact",
                    "primary_output": code_path,
                    "required_read_paths": [req_doc, test_doc],
                    "required_write_paths": [code_path],
                }
            },
        },
    ]


def _write_epic(root: Path, *, model: str, issues: list[dict[str, Any]]) -> None:
    payload = {
        "id": EPIC_ID,
        "name": EPIC_ID,
        "type": "epic",
        "status": "ready",
        "team": TEAM_NAME,
        "environment": ENV_NAME,
        "description": "Probe-only bad-requirements to code generation chain.",
        "architecture_governance": {"idesign": False, "pattern": "Probe"},
        "params": {
            "model_overrides": {
                "requirements_analyst": model,
                "coder": model,
                "code_reviewer": model,
                "integrity_guard": model,
            }
        },
        "issues": issues,
    }
    write_json(root / "model" / "core" / "epics" / f"{EPIC_ID}.json", payload)


def _prepare_runtime_root(
    workspace: Path,
    *,
    model: str,
    temperature: float,
    seed: int,
    timeout: int,
    bad_requirements_text: str,
) -> list[dict[str, Any]]:
    issues = _issue_payloads()
    write_probe_runtime_root(
        workspace,
        epic_id=EPIC_ID,
        environment_model=model,
        issues=[],
        team_name=TEAM_NAME,
        role_name="requirements_analyst",
        temperature=temperature,
        seed=seed,
        timeout=timeout,
    )
    _write_role(
        workspace,
        role_name="requirements_analyst",
        description="Turn messy input into a clean requirements artifact. Do not invent hidden authority.",
        tools=["read_file", "write_file", "list_directory", "add_issue_comment", "get_issue_context", "update_issue_status"],
    )
    _write_role(
        workspace,
        role_name="coder",
        description="Implement the requested artifact from the refined requirements and keep paths truthful.",
        tools=["read_file", "write_file", "list_directory", "add_issue_comment", "get_issue_context", "update_issue_status"],
    )
    _write_role(
        workspace,
        role_name="code_reviewer",
        description="Review produced artifacts and advance or block the issue truthfully.",
        tools=["read_file", "list_directory", "add_issue_comment", "get_issue_context", "update_issue_status"],
    )
    _write_role(
        workspace,
        role_name="integrity_guard",
        description="Final gatekeeper for probe issues. Mark done only when requested artifacts are present and acceptable.",
        tools=["read_file", "list_directory", "update_issue_status"],
    )
    _write_team(workspace)
    _write_epic(workspace, model=model, issues=issues)
    req_path = workspace / "input" / "bad_requirements.txt"
    req_path.parent.mkdir(parents=True, exist_ok=True)
    req_path.write_text(bad_requirements_text.strip() + "\n", encoding="utf-8")
    return issues


def _event_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        name = str(row.get("event") or "").strip()
        if not name:
            continue
        counts[name] = counts.get(name, 0) + 1
    return counts


def _artifact_presence(workspace: Path) -> dict[str, bool]:
    wanted = [
        "input/bad_requirements.txt",
        "agent_output/requirements.md",
        "agent_output/acceptance_tests.md",
        "agent_output/main.py",
    ]
    return {path: (workspace / path).exists() for path in wanted}


async def _run_chain(
    *,
    workspace: Path,
    provider: str,
    model: str,
    temperature: float,
    seed: int,
    timeout: int,
    bad_requirements_text: str,
    ollama_host: str,
    openai_base_url: str,
    openai_api_key: str,
) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    issues = _prepare_runtime_root(
        workspace,
        model=model,
        temperature=temperature,
        seed=seed,
        timeout=timeout,
        bad_requirements_text=bad_requirements_text,
    )
    session_id = f"req-to-code-{_safe_token(workspace.name)}-{_safe_token(provider)}"
    build_id = f"build-req-to-code-{_safe_token(workspace.name)}-{_safe_token(provider)}"

    extra_env: dict[str, str] = {}
    if openai_base_url:
        extra_env["ORKET_LLM_OPENAI_BASE_URL"] = openai_base_url
    if openai_api_key:
        extra_env["ORKET_LLM_OPENAI_API_KEY"] = openai_api_key

    pipeline_result: Any = None
    issue_rows: list[Any] = []
    run_error: Exception | None = None

    with applied_probe_env(
        provider=provider,
        ollama_host=ollama_host.strip() or None,
        disable_sandbox=True,
        extra_env=extra_env or None,
    ):
        pipeline = ExecutionPipeline(
            workspace=workspace,
            department="core",
            config_root=workspace,
            run_ledger_repo=AsyncProtocolRunLedgerRepository(workspace),
        )
        try:
            pipeline_result = await pipeline.run_card(EPIC_ID, session_id=session_id, build_id=build_id)
        except Exception as exc:  # noqa: BLE001
            run_error = exc
            if is_environment_blocker(exc):
                raise
        try:
            issue_rows = await pipeline.async_cards.get_by_build(build_id)
        except Exception:  # noqa: BLE001
            issue_rows = []

    summary = run_summary(workspace, session_id)
    proto = protocol_events(workspace, session_id)
    rt = runtime_events(workspace, session_id)
    inventory = observability_inventory(workspace, session_id)

    return {
        "schema_version": "probe.requirements_to_code_chain.v1",
        "recorded_at_utc": now_utc_iso(),
        "observed_result": "environment blocker"
        if run_error and is_environment_blocker(run_error)
        else ("success" if str((summary or {}).get("status") or "") == "done" else "partial success"),
        "requested_provider": provider,
        "requested_model": model,
        "workspace": str(workspace),
        "session_id": session_id,
        "build_id": build_id,
        "issues_requested": issues,
        "run_summary": summary,
        "protocol_events": {
            "count": len(proto),
            "run_finalized_observed": any(str(row.get("kind") or "") == "run_finalized" for row in proto),
        },
        "runtime_events": {
            "count": len(rt),
            "event_counts": _event_counts(rt),
        },
        "artifacts": _artifact_presence(workspace),
        "issue_statuses": [
            {
                "id": str(getattr(issue, "id", "")),
                "status": getattr(getattr(issue, "status", None), "value", getattr(issue, "status", None)),
            }
            for issue in issue_rows
        ],
        "pipeline_result": str(pipeline_result),
        "observability_inventory": inventory,
        "error_type": type(run_error).__name__ if run_error else "",
        "error": str(run_error) if run_error else "",
    }


def _python_cmd() -> list[str]:
    return [sys.executable]


def _run_subprocess(
    label: str,
    cmd: list[str],
    *,
    env_updates: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    env = os.environ.copy()
    if env_updates:
        env.update({k: v for k, v in env_updates.items() if v is not None})
    result = subprocess.run(
        cmd,
        cwd=str(cwd or REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "label": label,
        "command": cmd,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _run_preflight(*, provider: str, model: str, output_path: Path, ollama_host: str, openai_base_url: str) -> dict[str, Any]:
    cmd = _python_cmd() + [
        str(REPO_ROOT / "scripts" / "providers" / "check_model_provider_preflight.py"),
        "--provider",
        provider,
        "--model-id",
        model,
        "--auto-select-model",
        "--smoke-stream",
        "--json",
    ]
    if provider == "ollama" and ollama_host:
        cmd += ["--ollama-host", ollama_host]
    if provider == "lmstudio" and openai_base_url:
        cmd += ["--openai-base-url", openai_base_url]
    result = _run_subprocess(f"preflight:{provider}:{model}", cmd)
    _write_json(output_path, result)
    return result


def _run_baseline(*, provider: str, model: str, workspace: Path, output_path: Path, ollama_host: str, openai_base_url: str) -> dict[str, Any]:
    cmd = _python_cmd() + [
        str(REPO_ROOT / "scripts" / "probes" / "p01_single_issue.py"),
        "--workspace",
        str(workspace),
        "--execution-profile",
        "builder_guard_artifact_v1",
        "--artifact-path",
        "agent_output/fibonacci.py",
        "--provider",
        provider,
        "--model",
        model,
        "--json",
    ]
    env_updates = {"ORKET_DISABLE_SANDBOX": "1"}
    if provider == "ollama" and ollama_host:
        env_updates["OLLAMA_HOST"] = ollama_host
    if provider == "lmstudio" and openai_base_url:
        env_updates["ORKET_LLM_OPENAI_BASE_URL"] = openai_base_url
    result = _run_subprocess(f"baseline:{provider}:{model}", cmd, env_updates=env_updates)
    _write_json(output_path, result)
    return result


def _default_pairs(args: argparse.Namespace) -> list[PairSpec]:
    pairs = [PairSpec(name="primary", ollama_model=args.ollama_model, lmstudio_model=args.lmstudio_model)]
    if args.ollama_model_2 and args.lmstudio_model_2:
        pairs.append(PairSpec(name="secondary", ollama_model=args.ollama_model_2, lmstudio_model=args.lmstudio_model_2))
    return pairs


def _provider_runs_for_pair(args: argparse.Namespace, pair: PairSpec) -> list[ProviderRun]:
    base_output = Path(args.output_dir).resolve() / pair.name
    base_workspace = Path(args.workspace_root).resolve() / pair.name
    return [
        ProviderRun(
            label=f"{pair.name}.ollama",
            provider="ollama",
            model=pair.ollama_model,
            workspace=base_workspace / "ollama",
            preflight_output=base_output / "ollama.preflight.json",
            baseline_output=base_output / "ollama.baseline.json",
            chain_output=base_output / "ollama.chain.json",
        ),
        ProviderRun(
            label=f"{pair.name}.lmstudio",
            provider="lmstudio",
            model=pair.lmstudio_model,
            workspace=base_workspace / "lmstudio",
            preflight_output=base_output / "lmstudio.preflight.json",
            baseline_output=base_output / "lmstudio.baseline.json",
            chain_output=base_output / "lmstudio.chain.json",
        ),
    ]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run sequential local-provider codegen comparisons from repo_root/scripts.")
    parser.add_argument("--ollama-model", required=True, help="Primary Ollama model id.")
    parser.add_argument("--lmstudio-model", required=True, help="Primary LM Studio model id.")
    parser.add_argument("--ollama-model-2", default="", help="Optional second Ollama model id.")
    parser.add_argument("--lmstudio-model-2", default="", help="Optional second LM Studio model id.")
    parser.add_argument("--ollama-host", default="http://localhost:11434")
    parser.add_argument("--openai-base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--openai-api-key", default="lm-studio")
    parser.add_argument("--workspace-root", default=str(REPO_ROOT / ".probe_workspace" / "provider_codegen_matrix"))
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "benchmarks" / "results" / "probes" / "provider_codegen_matrix"))
    parser.add_argument("--requirements-file", default="", help="Optional path to a custom bad requirements text file.")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--skip-baseline", action="store_true")
    parser.add_argument("--skip-chain", action="store_true")
    parser.add_argument("--clean", action="store_true", help="Delete prior workspaces/output dirs for the selected pair names before running.")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def _load_requirements_text(path: str) -> str:
    if not path:
        return DEFAULT_REQUIREMENTS
    return Path(path).read_text(encoding="utf-8")


def _summarize_chain(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "observed_result": payload.get("observed_result"),
        "artifacts": payload.get("artifacts"),
        "issue_statuses": payload.get("issue_statuses"),
        "runtime_event_counts": ((payload.get("runtime_events") or {}).get("event_counts") or {}),
        "error_type": payload.get("error_type"),
        "error": payload.get("error"),
    }


def _pair_report(pair: PairSpec, runs: list[ProviderRun], stage_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {"pair": pair.name, "models": {}, "steps": {}}
    for run in runs:
        payload["models"][run.provider] = run.model
        provider_steps = stage_results.get(run.label, {})
        payload["steps"][run.provider] = {
            "preflight_returncode": ((provider_steps.get("preflight") or {}).get("returncode")),
            "baseline_returncode": ((provider_steps.get("baseline") or {}).get("returncode")),
            "chain": _summarize_chain(provider_steps.get("chain") or {}),
            "paths": {
                "workspace": str(run.workspace),
                "preflight_output": str(run.preflight_output),
                "baseline_output": str(run.baseline_output),
                "chain_output": str(run.chain_output),
            },
        }
    return payload


def main() -> int:
    args = _parse_args()
    pairs = _default_pairs(args)
    requirements_text = _load_requirements_text(args.requirements_file)
    stage_results: dict[str, dict[str, Any]] = {}
    summary_pairs: list[dict[str, Any]] = []

    for pair in pairs:
        runs = _provider_runs_for_pair(args, pair)
        if args.clean:
            for run in runs:
                shutil.rmtree(run.workspace, ignore_errors=True)
                shutil.rmtree(run.preflight_output.parent, ignore_errors=True)

        for run in runs:
            stage_results.setdefault(run.label, {})
            if not args.skip_preflight:
                preflight = _run_preflight(
                    provider=run.provider,
                    model=run.model,
                    output_path=run.preflight_output,
                    ollama_host=args.ollama_host,
                    openai_base_url=args.openai_base_url,
                )
                stage_results[run.label]["preflight"] = preflight

            if not args.skip_baseline:
                baseline_workspace = run.workspace.parent / f"{run.workspace.name}_baseline"
                baseline = _run_baseline(
                    provider=run.provider,
                    model=run.model,
                    workspace=baseline_workspace,
                    output_path=run.baseline_output,
                    ollama_host=args.ollama_host,
                    openai_base_url=args.openai_base_url,
                )
                stage_results[run.label]["baseline"] = baseline

            if not args.skip_chain:
                try:
                    chain = asyncio.run(
                        _run_chain(
                            workspace=run.workspace,
                            provider=run.provider,
                            model=run.model,
                            temperature=args.temperature,
                            seed=args.seed,
                            timeout=args.timeout,
                            bad_requirements_text=requirements_text,
                            ollama_host=args.ollama_host,
                            openai_base_url=args.openai_base_url,
                            openai_api_key=args.openai_api_key,
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    chain = {
                        "schema_version": "probe.requirements_to_code_chain.v1",
                        "recorded_at_utc": now_utc_iso(),
                        "observed_result": "environment blocker" if is_environment_blocker(exc) else "failure",
                        "requested_provider": run.provider,
                        "requested_model": run.model,
                        "workspace": str(run.workspace),
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                _write_json(run.chain_output, chain)
                stage_results[run.label]["chain"] = chain

        summary_pairs.append(_pair_report(pair, runs, stage_results))

    final_payload = {
        "schema_version": "probe.provider_codegen_matrix.v1",
        "recorded_at_utc": now_utc_iso(),
        "repo_root": str(REPO_ROOT),
        "pairs": summary_pairs,
    }
    summary_path = Path(args.output_dir).resolve() / "summary.json"
    _write_json(summary_path, final_payload)

    if args.json:
        print(json.dumps({"summary_path": str(summary_path), **final_payload}, indent=2, ensure_ascii=True))
    else:
        print(f"summary={summary_path}")

    any_chain_success = False
    for pair in summary_pairs:
        for provider_steps in (pair.get("steps") or {}).values():
            observed = (((provider_steps.get("chain") or {}).get("observed_result")))
            if observed in {"success", "partial success"}:
                any_chain_success = True
    return 0 if any_chain_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
