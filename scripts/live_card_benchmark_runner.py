from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one benchmark task through the live Orket card pipeline.")
    parser.add_argument("--task", required=True, help="Path to benchmark task JSON.")
    parser.add_argument("--venue", default="local-hardware")
    parser.add_argument("--flow", default="live")
    parser.add_argument("--run-dir", default="", help="Workspace/run directory.")
    parser.add_argument("--runs-root", default="workspace/runs", help="Durable root for indexed run artifacts.")
    parser.add_argument("--department", default="core")
    return parser.parse_args()


def _build_epic(task: dict, task_context_file: str, output_file: str) -> dict:
    task_id = str(task.get("id", "unknown"))
    instruction = str(task.get("instruction", "")).strip()
    description = str(task.get("description", "")).strip()
    acceptance = task.get("acceptance_contract", {})
    mode = str(acceptance.get("mode", "")).strip().lower()
    pass_conditions = acceptance.get("pass_conditions", [])
    pass_text = "; ".join(str(item) for item in pass_conditions if str(item).strip()) or "Task-level checks pass."
    problem = str(task.get("problem", "")).strip()
    function_signature = str(task.get("function_signature", "")).strip()
    constraints = [str(item).strip() for item in (task.get("constraints") or []) if str(item).strip()]
    io_examples = task.get("io_examples") or []
    evaluation = task.get("evaluation") or {}

    # Include task instruction directly in summary because the default prompt includes
    # issue summary but may omit "note" details in some configurations.
    summary_suffix = instruction or description or "No explicit task instruction provided."
    if mode == "function":
        preferred_signature = function_signature or "def deterministic_function(input_value):"
        summary_suffix = (
            f"{summary_suffix} "
            "Quality contract: implement at least one non-trivial function body with >=2 meaningful statements, "
            "use function input parameters in computation, and do not return constant-only stub values."
        )
        summary_suffix = (
            f"{summary_suffix} "
            "Code-shape contract: output focused implementation code in agent_output/main.py only. "
            "Do not emit CLI wrappers, crash handlers, orchestration boilerplate, or placeholder comments."
        )
        summary_suffix = (
            f"{summary_suffix} "
            "Output contract: return exact required values with no extra characters, separators, or whitespace changes. "
            "When returning collections, apply stable deterministic ordering for all levels so repeated runs are identical "
            "and ordering-sensitive checks pass."
        )
        summary_suffix = (
            f"{summary_suffix} "
            "For nested list/group outputs, sort each inner group deterministically and then sort the outer list "
            "by a stable key (for example first element, then length) before returning."
        )
        summary_suffix = (
            f"{summary_suffix} "
            f"Implement exactly one top-level function matching signature {preferred_signature} "
            "that performs deterministic computation using at least one intermediate variable assignment "
            "before returning a computed value."
        )
        if function_signature:
            summary_suffix = f"{summary_suffix} Required function signature: {function_signature}."
        if problem:
            summary_suffix = f"{summary_suffix} Problem: {problem}."
        eval_examples = evaluation.get("examples") if isinstance(evaluation, dict) else None
        if isinstance(eval_examples, list) and eval_examples:
            summary_suffix = (
                f"{summary_suffix} "
                f"Evaluation examples (must match exactly): {json.dumps(eval_examples, ensure_ascii=False)}."
            )
    return {
        "name": "",
        "description": f"Live benchmark task {task_id}",
        "status": "ready",
        "team": "standard",
        "environment": "standard",
        "issues": [
            {
                "id": f"LB-{task_id}-1",
                "summary": f"Execute benchmark task {task_id}: {summary_suffix}",
                "seat": "coder",
                "status": "ready",
                "priority": "High",
                "note": (
                    f"Read {task_context_file}. Then write {output_file}. "
                    "The output must include task id, summary, implementation plan, and acceptance checks. "
                    "If any file is missing, create it instead of failing. "
                    "Main code style requirements: concise and task-focused; avoid comments unless strictly necessary; "
                    "no __main__ entrypoint unless the task explicitly requires runtime CLI behavior; "
                    "for function-mode tasks avoid print statements and follow the required function signature. "
                    "For function-mode tasks, return exact expected output format with no additional characters; "
                    "if returning list/dict/set-derived data, normalize to deterministic ordering before return. "
                    f"Description: {description} "
                    f"Instruction: {instruction or 'No explicit instruction provided; use description and acceptance contract.'} "
                    f"Pass conditions: {pass_text} "
                    f"Problem statement: {problem or 'Not provided.'} "
                    f"Function signature: {function_signature or 'Not provided.'} "
                    f"Constraints: {'; '.join(constraints) if constraints else 'Not provided.'} "
                    f"I/O examples: {json.dumps(io_examples, ensure_ascii=False) if io_examples else 'Not provided.'}"
                ),
            }
        ],
    }


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso_z(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _parse_session_id(orket_log_path: Path) -> str:
    if not orket_log_path.exists():
        return ""
    session_id = ""
    for line in orket_log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(row.get("event", "")).strip() != "session_start":
            continue
        data = row.get("data") or {}
        run_id = str(data.get("run_id", "")).strip()
        if run_id:
            session_id = run_id
    return session_id


def _safe_copy(src: Path, dst: Path) -> None:
    if not src.exists() or not src.is_file():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _safe_copy_tree(src: Path, dst: Path) -> None:
    if not src.exists() or not src.is_dir():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst)


def _is_placeholder_source(text: str) -> bool:
    lowered = text.lower()
    patterns = (
        "placeholder",
        "todo",
        "lorem ipsum",
        "stub implementation",
        "dummy implementation",
    )
    return any(token in lowered for token in patterns)


def _validate_task_outputs(run_dir: Path, task: dict[str, Any], output_file: str) -> list[str]:
    issues: list[str] = []
    expected_main = run_dir / "agent_output" / "main.py"
    if not expected_main.exists():
        issues.append("missing agent_output/main.py")
    else:
        source = expected_main.read_text(encoding="utf-8", errors="replace")
        if _is_placeholder_source(source):
            issues.append("agent_output/main.py contains placeholder patterns")
    output_path = run_dir / output_file
    if not output_path.exists():
        issues.append(f"missing {output_file}")
    acceptance = task.get("acceptance_contract") or {}
    required_artifacts = acceptance.get("required_artifacts") or []
    for artifact in required_artifacts:
        rel = str(artifact or "").strip()
        if not rel:
            continue
        candidate = run_dir / rel
        if not candidate.exists():
            issues.append(f"missing required artifact: {rel}")
    report_path = run_dir / "report.json"
    if report_path.exists():
        try:
            report_payload = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            issues.append("report.json is unreadable")
        else:
            qc = report_payload.get("quality_checks")
            if not isinstance(qc, dict):
                issues.append("report.json missing quality_checks")
            elif not bool(qc.get("passed", False)):
                reason = str(qc.get("reason", "")).strip()
                issues.append(f"quality checks failed: {reason or 'unspecified'}")
    return issues


def _count_meaningful_statements(func: ast.FunctionDef) -> int:
    def _is_docstring_expr(node: ast.stmt) -> bool:
        return (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )

    count = 0
    for node in ast.walk(func):
        if not isinstance(node, ast.stmt):
            continue
        if node is func:
            continue
        if isinstance(node, ast.FunctionDef):
            continue
        if isinstance(node, ast.Pass):
            continue
        if _is_docstring_expr(node):
            continue
        count += 1
    return count


def _evaluate_quality(task: dict[str, Any], main_text: str) -> dict[str, Any]:
    acceptance = task.get("acceptance_contract") or {}
    mode = str(acceptance.get("mode", "")).strip().lower()
    checks: list[dict[str, Any]] = []
    parsed_module: ast.Module | None = None
    required_keywords = [
        str(item).strip()
        for item in (acceptance.get("quality_required_keywords") or [])
        if str(item).strip()
    ]
    forbidden_keywords = [
        str(item).strip()
        for item in (
            acceptance.get("quality_forbidden_keywords")
            or [
                "orket.interfaces.cli",
                "run_cli",
                "log_crash",
                "[CRITICAL ERROR]",
                "asyncio.run(run_cli())",
                "__main__",
                "def main(",
                "print(",
            ]
        )
        if str(item).strip()
    ]

    if not main_text.strip():
        checks.append({"name": "non_empty_main", "passed": False, "detail": "agent_output/main.py is empty"})
    else:
        checks.append({"name": "non_empty_main", "passed": True, "detail": "main.py is non-empty"})

    try:
        parsed_module = ast.parse(main_text or "")
        checks.append({"name": "python_parseable", "passed": True, "detail": "main.py parsed successfully"})
    except SyntaxError as exc:
        checks.append({"name": "python_parseable", "passed": False, "detail": f"syntax error: {exc.msg}"})

    lowered_text = main_text.lower()
    if mode == "function" and not required_keywords:
        required_keywords = ["def ", "return"]
    if required_keywords:
        missing_required = [kw for kw in required_keywords if kw.lower() not in lowered_text]
        checks.append(
            {
                "name": "required_keywords_present",
                "passed": len(missing_required) == 0,
                "detail": "all required keywords present"
                if not missing_required
                else f"missing required keywords: {', '.join(missing_required)}",
            }
        )

    hit_forbidden = [kw for kw in forbidden_keywords if kw.lower() in lowered_text]
    checks.append(
        {
            "name": "forbidden_keywords_absent",
            "passed": len(hit_forbidden) == 0,
            "detail": "no forbidden keywords detected"
            if not hit_forbidden
            else f"forbidden keywords detected: {', '.join(hit_forbidden)}",
        }
    )

    if mode == "function" and parsed_module is not None:
        funcs = [node for node in parsed_module.body if isinstance(node, ast.FunctionDef)]
        checks.append(
            {
                "name": "has_function_definition",
                "passed": bool(funcs),
                "detail": "found function definitions" if funcs else "no top-level function definitions found",
            }
        )
        if funcs:
            meaningful_counts = [_count_meaningful_statements(fn) for fn in funcs]
            has_non_trivial = any(count >= 2 for count in meaningful_counts)
            checks.append(
                {
                    "name": "non_trivial_function_body",
                    "passed": has_non_trivial,
                    "detail": "at least one function has >=2 meaningful statements"
                    if has_non_trivial
                    else "all functions are trivial (single/pass/docstring-only)",
                }
            )

            has_param_usage = False
            has_constant_only_return = True
            has_param_non_trivial = False
            for fn in funcs:
                params = {
                    arg.arg
                    for arg in (
                        list(fn.args.posonlyargs)
                        + list(fn.args.args)
                        + list(fn.args.kwonlyargs)
                    )
                }
                if fn.args.vararg:
                    params.add(fn.args.vararg.arg)
                if fn.args.kwarg:
                    params.add(fn.args.kwarg.arg)
                if params:
                    param_refs = {
                        node.id
                        for node in ast.walk(fn)
                        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                    }
                    fn_uses_params = any(name in param_refs for name in params)
                    if fn_uses_params:
                        has_param_usage = True
                        if _count_meaningful_statements(fn) >= 2:
                            has_param_non_trivial = True
                returns = [node for node in ast.walk(fn) if isinstance(node, ast.Return)]
                if not returns:
                    has_constant_only_return = False
                else:
                    # Boolean-return predicates are valid for many benchmark tasks.
                    if all(
                        (ret.value is not None and isinstance(ret.value, ast.Constant) and isinstance(ret.value.value, bool))
                        for ret in returns
                    ):
                        has_constant_only_return = False
                        continue
                    if not all(
                        (ret.value is not None and isinstance(ret.value, ast.Constant))
                        for ret in returns
                    ):
                        has_constant_only_return = False

            checks.append(
                {
                    "name": "uses_function_parameters",
                    "passed": has_param_usage,
                    "detail": "at least one function uses its parameters"
                    if has_param_usage
                    else "function output appears independent of input parameters",
                }
            )
            checks.append(
                {
                    "name": "not_constant_return_stub",
                    "passed": not has_constant_only_return,
                    "detail": "returns are not constant-only stubs"
                    if not has_constant_only_return
                    else "all return statements are constant literals",
                }
            )
            checks.append(
                {
                    "name": "has_parameterized_non_trivial_function",
                    "passed": has_param_non_trivial,
                    "detail": "at least one function both uses parameters and has >=2 meaningful statements"
                    if has_param_non_trivial
                    else "no function combines parameter usage with non-trivial logic",
                }
            )

    # Optional behavior checks against explicit examples from task specification.
    evaluation = task.get("evaluation") or {}
    eval_type = str(evaluation.get("type", "")).strip().lower()
    if eval_type == "function_examples":
        function_name = str(evaluation.get("function_name", "")).strip()
        examples = evaluation.get("examples") or []
        if not function_name:
            checks.append(
                {
                    "name": "example_cases_pass",
                    "passed": False,
                    "detail": "evaluation.function_name missing",
                }
            )
        elif not isinstance(examples, list) or not examples:
            checks.append(
                {
                    "name": "example_cases_pass",
                    "passed": False,
                    "detail": "evaluation.examples missing",
                }
            )
        else:
            with tempfile.TemporaryDirectory(prefix="orket_eval_") as temp_dir:
                temp_path = Path(temp_dir)
                target_path = temp_path / "candidate.py"
                target_path.write_text(main_text, encoding="utf-8")
                cases_path = temp_path / "cases.json"
                cases_path.write_text(json.dumps(examples), encoding="utf-8")
                checker_path = temp_path / "checker.py"
                checker_path.write_text(
                    "\n".join(
                        [
                            "import importlib.util",
                            "import json",
                            "import sys",
                            "",
                            "target, fn_name, cases_file = sys.argv[1], sys.argv[2], sys.argv[3]",
                            "spec = importlib.util.spec_from_file_location('candidate', target)",
                            "if spec is None or spec.loader is None:",
                            "    print(json.dumps({'ok': False, 'error': 'module_load_failed'}))",
                            "    raise SystemExit(2)",
                            "mod = importlib.util.module_from_spec(spec)",
                            "spec.loader.exec_module(mod)",
                            "if not hasattr(mod, fn_name):",
                            "    print(json.dumps({'ok': False, 'error': f'missing_function:{fn_name}'}))",
                            "    raise SystemExit(3)",
                            "fn = getattr(mod, fn_name)",
                            "cases = json.loads(open(cases_file, 'r', encoding='utf-8').read())",
                            "for idx, case in enumerate(cases):",
                            "    args = case.get('args', [])",
                            "    kwargs = case.get('kwargs', {})",
                            "    expected = case.get('expected')",
                            "    actual = fn(*args, **kwargs)",
                            "    if actual != expected:",
                            "        print(json.dumps({'ok': False, 'error': 'mismatch', 'index': idx, 'expected': expected, 'actual': actual}))",
                            "        raise SystemExit(4)",
                            "print(json.dumps({'ok': True, 'count': len(cases)}))",
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
                try:
                    result = subprocess.run(
                        ["python", str(checker_path), str(target_path), function_name, str(cases_path)],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=5,
                    )
                except subprocess.TimeoutExpired:
                    checks.append(
                        {
                            "name": "example_cases_pass",
                            "passed": False,
                            "detail": "example evaluation timed out",
                        }
                    )
                else:
                    payload_text = (result.stdout or "").strip()
                    detail = payload_text if payload_text else (result.stderr or "evaluation failed")
                    checks.append(
                        {
                            "name": "example_cases_pass",
                            "passed": int(result.returncode) == 0,
                            "detail": detail,
                        }
                    )

    passed = all(bool(check.get("passed")) for check in checks)
    failed_names = [str(check.get("name")) for check in checks if not bool(check.get("passed"))]
    reason = "ok" if passed else "; ".join(failed_names)
    return {
        "mode": mode or "unspecified",
        "passed": passed,
        "reason": reason,
        "checks": checks,
    }


def _materialize_required_artifacts(
    run_dir: Path,
    task: dict[str, Any],
    task_id: str,
    output_file: str,
    *,
    process_exit_code: int,
    started_at: datetime,
    ended_at: datetime,
) -> dict[str, Any]:
    acceptance = task.get("acceptance_contract") or {}
    required_artifacts = [str(x).strip() for x in (acceptance.get("required_artifacts") or []) if str(x).strip()]
    main_path = run_dir / "agent_output" / "main.py"
    main_text = main_path.read_text(encoding="utf-8", errors="replace") if main_path.exists() else ""
    main_sha = hashlib.sha256(main_text.encode("utf-8")).hexdigest() if main_text else ""
    duration_ms = int((ended_at - started_at).total_seconds() * 1000.0)
    quality_checks = _evaluate_quality(task=task, main_text=main_text)

    output_md_path = run_dir / output_file
    if not output_md_path.exists():
        lines = [
            f"# Benchmark Task {task_id} Output",
            "",
            "## Summary",
            f"- Task ID: {task_id}",
            f"- Description: {str(task.get('description', '')).strip()}",
            f"- Instruction: {str(task.get('instruction', '')).strip()}",
            f"- Process exit code: {int(process_exit_code)}",
            f"- Duration ms: {duration_ms}",
            f"- Generated at UTC: {_iso_z(ended_at)}",
            "",
            "## Implementation",
            f"- Main path: agent_output/main.py",
            f"- Quality checks passed: {quality_checks['passed']}",
            f"- Quality reason: {quality_checks['reason']}",
            "",
            "## Acceptance Contract",
        ]
        for cond in (acceptance.get("pass_conditions") or []):
            lines.append(f"- {str(cond)}")
        if not (acceptance.get("pass_conditions") or []):
            lines.append("- Task-level checks pass.")
        output_md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    if "run.log" in required_artifacts:
        run_log_path = run_dir / "run.log"
        if not run_log_path.exists():
            run_log_path.write_text(
                "\n".join(
                    [
                        f"task_id={task_id}",
                        f"process_exit_code={int(process_exit_code)}",
                        f"duration_ms={duration_ms}",
                        f"generated_at_utc={_iso_z(ended_at)}",
                        f"quality_passed={str(bool(quality_checks.get('passed'))).lower()}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

    if "report.json" in required_artifacts:
        report_path = run_dir / "report.json"
        if not report_path.exists():
            payload = {
                "task_id": task_id,
                "generated_at_utc": _iso_z(ended_at),
                "process_exit_code": int(process_exit_code),
                "duration_ms": duration_ms,
                "artifacts": {
                    "benchmark_output": output_file,
                    "run_log": "run.log" if (run_dir / "run.log").exists() else "",
                    "report_json": "report.json",
                    "main_py": "agent_output/main.py" if main_path.exists() else "",
                },
                "main_sha256": main_sha,
                "quality_checks": quality_checks,
                "acceptance_contract": acceptance,
            }
            report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return quality_checks


def _extract_coder_final_message(run_dir: Path, session_id: str, task_id: str) -> str:
    if not session_id:
        return ""
    coder_message_path = (
        run_dir
        / "observability"
        / session_id
        / f"lb-{task_id}-1"
        / "001_coder"
        / "model_response.txt"
    )
    if not coder_message_path.exists():
        return ""
    return coder_message_path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    args = _parse_args()
    task_path = Path(args.task)
    task = json.loads(task_path.read_text(encoding="utf-8-sig"))
    task_id = str(task.get("id", "unknown"))
    task_id_padded = str(task_id).zfill(3) if str(task_id).isdigit() else str(task_id)
    started_at = _utc_now()
    run_id = uuid.uuid4().hex[:8]

    run_dir = Path(args.run_dir) if args.run_dir else task_path.parent
    run_dir.mkdir(parents=True, exist_ok=True)
    runs_root = Path(args.runs_root)
    runs_root.mkdir(parents=True, exist_ok=True)
    canonical_name = f"{started_at.strftime('%Y%m%d_%H%M%S')}_task{task_id_padded}_{run_id}"
    canonical_run_dir = runs_root / canonical_name
    canonical_run_dir.mkdir(parents=True, exist_ok=True)

    run_manifest_path = runs_root.parent / "run_manifest.jsonl"
    task_context_path = run_dir / "task_context.json"
    problem_statement_path = run_dir / "problem_statement.json"
    output_file = f"benchmark_task_{task_id}_output.md"
    task_context_path.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
    problem_statement = {
        "id": task.get("id"),
        "description": task.get("description"),
        "instruction": task.get("instruction"),
        "acceptance_contract": task.get("acceptance_contract") or {},
    }
    problem_statement_path.write_text(json.dumps(problem_statement, indent=2) + "\n", encoding="utf-8")

    epic_name = f"benchmark_live_{task_id}_{uuid.uuid4().hex[:8]}"
    epic_path = Path("model") / str(args.department) / "epics" / f"{epic_name}.json"
    epic_payload = _build_epic(
        task=task,
        task_context_file=task_context_path.name,
        output_file=output_file,
    )
    epic_payload["name"] = epic_name

    epic_path.parent.mkdir(parents=True, exist_ok=True)
    epic_path.write_text(json.dumps(epic_payload, indent=2) + "\n", encoding="utf-8")

    cmd = [
        "python",
        "main.py",
        "--epic",
        epic_name,
        "--department",
        str(args.department),
        "--workspace",
        str(run_dir),
    ]

    _append_jsonl(
        canonical_run_dir / "runtime_lifecycle.jsonl",
        {
            "event": "run_registered",
            "at_utc": _iso_z(started_at),
            "run_id": run_id,
            "task_id": task_id,
            "workspace": str(run_dir).replace("\\", "/"),
            "epic": epic_name,
        },
    )

    env = dict(os.environ)
    env.setdefault("ORKET_DISABLE_SANDBOX", "1")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    finally:
        try:
            epic_path.unlink(missing_ok=True)
        except OSError:
            pass

    # Persist command output as an artifact for harness hashing and troubleshooting.
    (run_dir / "live_runner_output.log").write_text(
        ((result.stdout or "") + "\n" + (result.stderr or "")).strip() + "\n",
        encoding="utf-8",
    )

    ended_at = _utc_now()
    orket_log_path = run_dir / "orket.log"
    session_id = _parse_session_id(orket_log_path)
    quality_checks = _materialize_required_artifacts(
        run_dir=run_dir,
        task=task,
        task_id=task_id,
        output_file=output_file,
        process_exit_code=int(result.returncode),
        started_at=started_at,
        ended_at=ended_at,
    )
    validation_issues = _validate_task_outputs(run_dir=run_dir, task=task, output_file=output_file)
    validation_passed = len(validation_issues) == 0 and int(result.returncode) == 0
    final_exit_code = 0 if validation_passed else 2

    final_main_path = run_dir / "agent_output" / "main.py"
    final_main_text = (
        final_main_path.read_text(encoding="utf-8", errors="replace") if final_main_path.exists() else ""
    )
    coder_final_message = _extract_coder_final_message(run_dir=run_dir, session_id=session_id, task_id=task_id_padded)

    runtime_event_payload = {
        "schema_version": "v1",
        "event": "coder_turn_finalized",
        "role": "system",
        "session_id": session_id,
        "issue_id": f"LB-{task_id_padded}-1",
        "turn_index": 0,
        "turn_trace_id": "",
        "selected_model": "",
        "prompt_id": "",
        "prompt_version": "",
        "prompt_checksum": "",
        "resolver_policy": "",
        "selection_policy": "",
        "guard_contract": None,
        "guard_decision": None,
        "terminal_reason": None,
        "duration_ms": int((ended_at - started_at).total_seconds() * 1000.0),
        "tokens": None,
    }
    _append_jsonl(canonical_run_dir / "runtime_lifecycle.jsonl", runtime_event_payload)
    _append_jsonl(
        canonical_run_dir / "runtime_lifecycle.jsonl",
        {
            "event": "run_artifacts_persisted",
            "at_utc": _iso_z(ended_at),
            "run_id": run_id,
            "task_id": task_id,
            "canonical_run_dir": str(canonical_run_dir).replace("\\", "/"),
        },
    )
    _append_jsonl(run_dir / "agent_output" / "observability" / "runtime_events.jsonl", runtime_event_payload)

    # Durable, queryable artifacts.
    _safe_copy(task_context_path, canonical_run_dir / "task_context.json")
    _safe_copy(problem_statement_path, canonical_run_dir / "problem_statement.json")
    _safe_copy(run_dir / "live_runner_output.log", canonical_run_dir / "live_runner_output.log")
    _safe_copy(orket_log_path, canonical_run_dir / "orket.log")
    _safe_copy(final_main_path, canonical_run_dir / "coder_final_main.py")
    if coder_final_message:
        (canonical_run_dir / "coder_final_message.txt").write_text(coder_final_message, encoding="utf-8")
    _safe_copy_tree(run_dir / "observability", canonical_run_dir / "observability")
    _safe_copy_tree(run_dir / "agent_output" / "verification", canonical_run_dir / "verification")

    run_meta = {
        "run_id": run_id,
        "session_id": session_id,
        "task_id": task_id,
        "issue_id": f"LB-{task_id_padded}-1",
        "started_at_utc": _iso_z(started_at),
        "ended_at_utc": _iso_z(ended_at),
        "duration_ms": int((ended_at - started_at).total_seconds() * 1000.0),
        "status": "passed" if validation_passed else "failed",
        "validation_passed": validation_passed,
        "validation_issues": validation_issues,
        "quality_checks": quality_checks,
        "workspace": str(run_dir).replace("\\", "/"),
        "canonical_run_dir": str(canonical_run_dir).replace("\\", "/"),
        "observability_path": str(canonical_run_dir / "observability" / session_id).replace("\\", "/")
        if session_id
        else "",
        "epic": epic_name,
        "model_map": {},
        "prompt_checksum": "",
        "venue": str(args.venue),
        "flow": str(args.flow),
        "department": str(args.department),
        "output_file": output_file,
        "final_main_path": str(canonical_run_dir / "coder_final_main.py").replace("\\", "/"),
    }
    if final_main_text:
        run_meta["final_main_sha256"] = hashlib.sha256(final_main_text.encode("utf-8")).hexdigest()

    (canonical_run_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2) + "\n", encoding="utf-8")
    _append_jsonl(run_manifest_path, run_meta)

    print(
        json.dumps(
            {
                "task_id": task_id,
                "exit_code": final_exit_code,
                "workspace": str(run_dir).replace("\\", "/"),
                "canonical_run_dir": str(canonical_run_dir).replace("\\", "/"),
                "run_manifest": str(run_manifest_path).replace("\\", "/"),
                "run_id": run_id,
                "session_id": session_id,
                "output_file": output_file,
                "validation_passed": validation_passed,
                "validation_issues": validation_issues,
            },
            sort_keys=True,
        )
    )
    return final_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
