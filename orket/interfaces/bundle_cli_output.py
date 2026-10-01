from __future__ import annotations

import json
from typing import Any

from orket.application.services.governed_run_demo_rendering import render_inspection, render_replay


def _render_review(result: dict[str, Any]) -> str:
    lines = [
        f"run_id: {result.get('run_id', '')}",
        f"deterministic decision: {result.get('deterministic_decision', '')}",
        f"artifact path: {result.get('artifact_dir', '')}",
    ]
    control_plane = result.get("control_plane")
    if isinstance(control_plane, dict):
        run_state = str(control_plane.get("run_state") or "").strip()
        attempt_state = str(control_plane.get("attempt_state") or "").strip()
        step_kind = str(control_plane.get("step_kind") or "").strip()
        summary_parts = []
        if run_state:
            summary_parts.append(f"run={run_state}")
        if attempt_state:
            summary_parts.append(f"attempt={attempt_state}")
        if step_kind:
            summary_parts.append(f"step={step_kind}")
        if summary_parts:
            lines.append(f"control-plane: {' '.join(summary_parts)}")
        ref_parts = []
        for field in ("run_id", "attempt_id", "step_id"):
            token = str(control_plane.get(field) or "").strip()
            if token:
                ref_parts.append(f"{field}={token}")
        if ref_parts:
            lines.append(f"control-plane refs: {' '.join(ref_parts)}")
    if bool(result.get("verbose")):
        lines.append(f"snapshot_digest: {result.get('snapshot_digest', '')}")
        lines.append(f"policy_digest: {result.get('policy_digest', '')}")
    return "\n".join(lines)


def _render_transaction(result: dict[str, Any]) -> str:
    output_lines: list[str] = []
    if result.get("plan"):
        output_lines.append(str(result["plan"]))
    advisories = result.get("advisories")
    if isinstance(advisories, list) and advisories:
        output_lines.append("FAILURE LESSON ADVISORIES:")
        for item in advisories:
            if not isinstance(item, dict):
                continue
            output_lines.append(
                f"  - [{item.get('score', '')}] {item.get('lesson_id', '')}: {item.get('summary', '')}"
            )
    preflight_warnings = result.get("preflight_warnings")
    if isinstance(preflight_warnings, list) and preflight_warnings:
        output_lines.append("PREFLIGHT WARNINGS:")
        for warning in preflight_warnings:
            output_lines.append(f"  - {warning}")
    status = "OK" if bool(result.get("ok")) else f"FAIL [{result.get('code')}]"
    output_lines.append(f"{status}: {result.get('message')}")
    parity = result.get("parity")
    if isinstance(parity, dict):
        output_lines.append(
            "PARITY: "
            + f"status={parity.get('status', '')}, "
            + f"changed_files={parity.get('changed_file_count', '')}"
        )
        if str(parity.get("artifact_path", "")).strip():
            output_lines.append(f"PARITY ARTIFACT: {parity['artifact_path']}")
    if result.get("verify_output_tail"):
        output_lines.append("")
        output_lines.append(str(result["verify_output_tail"]))
    return "\n".join(output_lines)


def render_human(result: dict[str, Any]) -> str:
    kind = str(result.get("kind") or "")
    if kind == "governed_run_execution":
        return str(result.get("console_output") or "")
    if kind == "governed_run_inspection":
        return render_inspection(result)
    if kind == "governed_run_replay":
        return render_replay(result)
    if kind == "governed_run_error":
        return f"FAIL [{result.get('code')}]: {result.get('message')}"

    if "deterministic_decision" in result and "artifact_dir" in result:
        return _render_review(result)

    if "extension_id" in result and "workload_count" in result:
        if bool(result.get("ok")):
            return (
                f"OK: {result.get('extension_id')} "
                f"(workloads={result.get('workload_count')}, warnings={result.get('warning_count', 0)})"
            )
        lines = [f"FAIL ({result.get('error_count', 0)} error(s))"]
        for item in result.get("errors", []):
            lines.append(f"[{item.get('code')}] {item.get('location')}: {item.get('message')}")
        return "\n".join(lines)

    if str(result.get("operation", "")) == "ext.init":
        if bool(result.get("ok")):
            return (
                f"OK: scaffolded external extension at {result.get('target')} "
                f"(files={result.get('copied_file_count', 0)})"
            )
        lines = [f"FAIL ({result.get('error_count', 0)} error(s))"]
        for item in result.get("errors", []):
            lines.append(f"[{item.get('code')}] {item.get('location')}: {item.get('message')}")
        return "\n".join(lines)

    if "code" in result and "message" in result:
        return _render_transaction(result)

    if bool(result.get("ok")):
        return f"OK: {result.get('manifest_name')} {result.get('manifest_version')} ({result.get('manifest_path')})"
    lines = [f"FAIL ({result.get('error_count', 0)} error(s))"]
    for item in result.get("errors", []):
        lines.append(f"[{item.get('code')}] {item.get('location')}: {item.get('message')}")
    return "\n".join(lines)


def emit_result(result: dict[str, Any], *, emit_json: bool) -> int:
    if emit_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(render_human(result))
    if isinstance(result.get("exit_code"), int):
        return int(result["exit_code"])
    return 0 if bool(result.get("ok")) else 1
