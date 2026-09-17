from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
    from scripts.governance.check_noop_critical_paths import (
        DEFAULT_SCAN_ROOTS,
        evaluate_noop_critical_paths,
    )
    from scripts.governance.enforce_test_taxonomy import evaluate_test_taxonomy
    from scripts.governance.export_dependency_graph import build_dependency_snapshot
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
    from scripts.governance.check_noop_critical_paths import (
        DEFAULT_SCAN_ROOTS,
        evaluate_noop_critical_paths,
    )
    from scripts.governance.enforce_test_taxonomy import evaluate_test_taxonomy
    from scripts.governance.export_dependency_graph import build_dependency_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = PROJECT_ROOT / "docs" / "projects" / "architectural-truth" / "architectural_truth_baseline.json"
EXCEPTION_REGISTER_PATH = (
    PROJECT_ROOT / "docs" / "projects" / "architectural-truth" / "ARCHITECTURE_EXCEPTION_REGISTER.json"
)
FATAL_MARKERS = ("[FATAL]", "[CRITICAL ERROR]", "Traceback (most recent call last)")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect the architectural-truth baseline without treating known debt as green."
    )
    parser.add_argument("--out", type=Path, default=OUTPUT_PATH, help="Stable JSON output path.")
    return parser.parse_args(argv)


def _run_command(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _command_observation(
    *,
    command_id: str,
    argv: list[str],
    cwd: Path,
    env: dict[str, str],
    expected_exit: int,
    stdin: str | None = None,
    required_claim: str = "",
    durable_effect: Path | None = None,
) -> dict[str, Any]:
    result = _run_command(argv, cwd=cwd, env=env, stdin=stdin)
    combined = result.stdout + result.stderr
    observed_fatal_markers = [marker for marker in FATAL_MARKERS if marker in combined]
    claim_present = not required_claim or required_claim in combined
    return {
        "command_id": command_id,
        "proof": "live_native_subprocess",
        "path": "primary",
        "result": "success" if result.returncode == expected_exit and claim_present else "failure",
        "exit_code": result.returncode,
        "expected_exit_code": expected_exit,
        "expected_exit_matched": result.returncode == expected_exit,
        "required_claim": required_claim or None,
        "required_claim_present": claim_present,
        "fatal_markers": observed_fatal_markers,
        "fatal_exit_truthful": not observed_fatal_markers or result.returncode != 0,
        "durable_effect_present": durable_effect.exists() if durable_effect is not None else None,
    }


def _runtime_command_observations(*, root: Path, env: dict[str, str]) -> list[dict[str, Any]]:
    runtime_command = [sys.executable, "-m", "orket.cli", "runtime"]
    return [
        _command_observation(
            command_id="installed_runtime_help_fresh_workspace",
            argv=[*runtime_command, "--help"],
            cwd=root,
            env=env,
            expected_exit=0,
            required_claim="usage: orket runtime",
            durable_effect=root / ".orket" / "durable" / "config" / "user_settings.json",
        ),
        _command_observation(
            command_id="installed_runtime_handled_fatal",
            argv=[*runtime_command, "extensions", "unsupported"],
            cwd=root,
            env=env,
            expected_exit=1,
            required_claim="orket runtime extensions list",
        ),
    ]


def _installed_command_observations(*, root: Path, env: dict[str, str]) -> list[dict[str, Any]]:
    module_prefix = [sys.executable, "-m"]
    return [
        _command_observation(
            command_id="bundle_cli_help",
            argv=[*module_prefix, "orket.interfaces.orket_bundle_cli", "--help"],
            cwd=root,
            env=env,
            expected_exit=0,
            required_claim="governed-run",
        ),
        _command_observation(
            command_id="prompts_cli_help",
            argv=[*module_prefix, "orket.interfaces.prompts_cli", "--help"],
            cwd=root,
            env=env,
            expected_exit=0,
            required_claim="Prompt asset tooling",
        ),
        _command_observation(
            command_id="quickstart_help",
            argv=[*module_prefix, "orket.quickstart.governed_action_demo", "--help"],
            cwd=root,
            env=env,
            expected_exit=0,
            required_claim="--decision",
        ),
        _command_observation(
            command_id="quickstart_eof",
            argv=[*module_prefix, "orket.quickstart.governed_action_demo", "--workspace", str(root)],
            cwd=root,
            env=env,
            stdin="",
            expected_exit=2,
            required_claim="E_QUICKSTART_INPUT_REQUIRED",
        ),
        _command_observation(
            command_id="governed_run_packaged_default",
            argv=[
                *module_prefix,
                "orket.interfaces.orket_bundle_cli",
                "demo",
                "governed-run",
                "--workspace",
                str(root),
            ],
            cwd=root,
            env=env,
            expected_exit=0,
            required_claim="[orket] Run completed",
            durable_effect=root / ".runs" / "governed-run-demo" / "evidence.json",
        ),
    ]


def collect_command_behavior() -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="orket-architectural-truth-") as raw_root:
        root = Path(raw_root)
        env = os.environ.copy()
        env["ORKET_DISABLE_SANDBOX"] = "1"
        env["ORKET_DURABLE_ROOT"] = str(root / ".orket" / "durable")
        env.pop("PYTEST_CURRENT_TEST", None)
        return [
            *_runtime_command_observations(root=root, env=env),
            *_installed_command_observations(root=root, env=env),
        ]


def collect_api_factory_behavior() -> dict[str, Any]:
    probe = """
import asyncio
import json
import tempfile
from pathlib import Path
import orket.interfaces.api as api_module
from orket.interfaces.api import create_api_app
with tempfile.TemporaryDirectory(prefix="orket-api-factory-probe-") as raw:
    root = Path(raw)
    first = create_api_app(root / "one")
    first_context = first.state.api_runtime_context
    second = create_api_app(root / "two")
    second_context = second.state.api_runtime_context
    print(json.dumps({
        "same_app_object": first is second,
        "first_context_replaced": first_context is not first.state.api_runtime_context,
        "first_root_retained": first_context.project_root == (root / "one").resolve(),
        "second_root_retained": second_context.project_root == (root / "two").resolve(),
        "distinct_contexts": first_context is not second_context,
        "distinct_engines": first_context.engine is not second_context.engine,
        "distinct_runtime_states": first_context.runtime_state is not second_context.runtime_state,
        "module_default_owner_absent": not hasattr(api_module, "app"),
    }, sort_keys=True))
    asyncio.run(first_context.close())
    asyncio.run(second_context.close())
"""
    env = os.environ.copy()
    env["ORKET_DISABLE_SANDBOX"] = "1"
    result = _run_command([sys.executable, "-c", probe], cwd=PROJECT_ROOT, env=env)
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    try:
        observation = json.loads(lines[-1]) if lines else {}
    except json.JSONDecodeError:
        observation = {}
    isolated = bool(
        observation
        and not observation.get("same_app_object", True)
        and not observation.get("first_context_replaced", True)
        and observation.get("first_root_retained")
        and observation.get("second_root_retained")
        and observation.get("distinct_contexts")
        and observation.get("distinct_engines")
        and observation.get("distinct_runtime_states")
        and observation.get("module_default_owner_absent")
    )
    return {
        "proof": "live_isolated_subprocess",
        "path": "primary",
        "result": "success" if result.returncode == 0 and isolated else "failure",
        "exit_code": result.returncode,
        **observation,
    }


def collect_size_inventory() -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    functions: list[dict[str, Any]] = []
    parse_errors: list[dict[str, str]] = []
    for path in sorted((PROJECT_ROOT / "orket").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        try:
            source = path.read_text(encoding="utf-8-sig")
            tree = ast.parse(source, filename=relative)
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            parse_errors.append({"path": relative, "error": str(exc)})
            continue
        line_count = len(source.splitlines())
        if line_count > 400:
            files.append({"path": relative, "lines": line_count})
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            function_lines = int((node.end_lineno or node.lineno) - node.lineno + 1)
            if function_lines > 70:
                functions.append(
                    {
                        "path": relative,
                        "line": int(node.lineno),
                        "name": node.name,
                        "lines": function_lines,
                    }
                )
    files.sort(key=lambda row: (-int(row["lines"]), str(row["path"])))
    functions.sort(key=lambda row: (-int(row["lines"]), str(row["path"]), int(row["line"])))
    return {
        "proof": "structural_ast",
        "python_files_scanned": sum(1 for path in (PROJECT_ROOT / "orket").rglob("*.py") if "__pycache__" not in path.parts),
        "files_over_400_total": len(files),
        "functions_over_70_total": len(functions),
        "largest_files": files[:25],
        "largest_functions": functions[:25],
        "parse_errors": parse_errors,
    }


def collect_ruff() -> dict[str, Any]:
    env = os.environ.copy()
    result = _run_command(
        [sys.executable, "-m", "ruff", "check", "orket", "--output-format", "json"],
        cwd=PROJECT_ROOT,
        env=env,
    )
    try:
        issues = json.loads(result.stdout)
    except json.JSONDecodeError:
        issues = []
    by_code = Counter(str(row.get("code") or "unknown") for row in issues if isinstance(row, dict))
    return {
        "proof": "structural_lint",
        "executed": result.returncode in {0, 1} and isinstance(issues, list),
        "exit_code": result.returncode,
        "issues_total": len(issues),
        "by_code": dict(sorted(by_code.items())),
    }


def load_exception_register() -> dict[str, Any]:
    payload = json.loads(EXCEPTION_REGISTER_PATH.read_text(encoding="utf-8"))
    owner = str(payload.get("owner") or "").strip()
    rows = list(payload.get("exceptions") or [])
    required = ("id", "area", "status", "reason", "removal_condition", "evidence")
    normalized = []
    invalid_ids = []
    seen_ids: set[str] = set()
    for row in rows:
        current = dict(row) if isinstance(row, dict) else {}
        current["owner"] = str(current.get("owner") or owner)
        row_id = str(current.get("id") or "")
        if row_id in seen_ids or any(not str(current.get(field) or "").strip() for field in (*required, "owner")):
            invalid_ids.append(row_id or "<missing>")
        seen_ids.add(row_id)
        normalized.append(current)
    return {
        "source": EXCEPTION_REGISTER_PATH.relative_to(PROJECT_ROOT).as_posix(),
        "schema_version": payload.get("schema_version"),
        "valid": bool(owner) and not invalid_ids,
        "invalid_ids": invalid_ids,
        "exceptions_total": len(normalized),
        "exceptions": normalized,
    }


def _summarize_taxonomy(payload: dict[str, Any]) -> dict[str, Any]:
    missing = list(payload.get("missing_layers") or [])
    return {
        "schema_version": payload.get("schema_version"),
        "tests_total": int(payload.get("tests_total") or 0),
        "missing_layer_total": int(payload.get("missing_layer_total") or 0),
        "by_layer": dict(payload.get("by_layer") or {}),
        "missing_layers_sample": missing[:100],
        "missing_layers_omitted": max(0, len(missing) - 100),
    }


def build_baseline() -> dict[str, Any]:
    dependency = build_dependency_snapshot()
    dependency.pop("generated_at", None)
    dependency["observed"] = {k: v for k, v in dependency["observed"].items() if k not in {"modules", "edges", "layers"}}
    taxonomy = _summarize_taxonomy(
        evaluate_test_taxonomy(root=PROJECT_ROOT / "tests")
    )
    no_op = evaluate_noop_critical_paths(
        roots=[PROJECT_ROOT / relative for relative in DEFAULT_SCAN_ROOTS]
    )
    exceptions = load_exception_register()
    commands = collect_command_behavior()
    false_success_commands = [
        row["command_id"]
        for row in commands
        if not bool(row.get("fatal_exit_truthful"))
    ]
    api_factory = collect_api_factory_behavior()
    ruff = collect_ruff()
    sizes = collect_size_inventory()
    collection_ok = (
        dependency["collection_ok"] and exceptions["valid"]
        and all(row["result"] == "success" for row in commands)
        and api_factory["result"] == "success"
        and ruff["executed"]
        and not sizes["parse_errors"]
    )
    return {
        "schema_version": "architectural_truth.baseline.v1",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "collection_ok": collection_ok,
        "release_ready": False,
        "release_ready_reason": "Active architectural exceptions and red/noisy proof gates remain.",
        "proof_boundary": {
            "commands": "live native subprocess",
            "api_factory": "live isolated subprocess",
            "dependency_taxonomy_noop_sizes_ruff": "structural",
        },
        "false_success_release_blocker": {
            "status": "clear" if not false_success_commands else "blocked",
            "blocked_commands": false_success_commands,
            "rule": "Fatal-shaped output must not return process exit 0.",
        },
        "command_behavior": commands,
        "api_factory_behavior": api_factory,
        "dependency_graph": dependency,
        "architecture_exceptions": exceptions,
        "test_taxonomy": taxonomy,
        "ruff": ruff,
        "size_inventory": sizes,
        "noop_critical_paths": no_op,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    payload = build_baseline()
    output_path = args.out.resolve()
    write_payload_with_diff_ledger(output_path, payload)
    print(f"Wrote {output_path}")
    print(
        "Architectural truth baseline collected: "
        f"collection_ok={str(payload['collection_ok']).lower()} "
        f"release_ready={str(payload['release_ready']).lower()}"
    )
    return 0 if bool(payload["collection_ok"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
