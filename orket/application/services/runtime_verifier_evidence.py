from __future__ import annotations

from typing import Any


_EVIDENCE_CLASSES = (
    "syntax_only",
    "command_execution",
    "behavioral_verification",
    "not_evaluated",
)


def annotate_runtime_verifier_evidence(
    *,
    checked_files: list[str],
    command_results: list[dict[str, Any]],
    stdout_contract: dict[str, Any],
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    annotated_results = [dict(item) for item in command_results if isinstance(item, dict)]
    behavioral_requested = bool(stdout_contract.get("expect_json_stdout")) or bool(stdout_contract.get("json_assertions"))
    behavioral_assertion_count = len(list(stdout_contract.get("json_assertions") or []))

    syntax_only_commands: list[dict[str, Any]] = []
    command_execution_commands: list[dict[str, Any]] = []
    behavioral_commands: list[dict[str, Any]] = []

    last_index = len(annotated_results) - 1
    for index, result in enumerate(annotated_results):
        command_id = str(result.get("command_id") or f"command:{index + 1:03d}")
        result["command_id"] = command_id
        evidence_class = "syntax_only" if _is_syntax_only_command(result) else "command_execution"
        if behavioral_requested and index == last_index:
            evidence_class = "behavioral_verification"
        result["evidence_class"] = evidence_class
        summary_row = _command_summary(result)
        if evidence_class == "syntax_only":
            syntax_only_commands.append(summary_row)
            continue
        if evidence_class == "behavioral_verification":
            behavioral_commands.append(summary_row)
            continue
        command_execution_commands.append(summary_row)

    syntax_only_evaluated = bool(checked_files or syntax_only_commands)
    command_execution_evaluated = bool(command_execution_commands)
    behavioral_evaluated = bool(behavioral_commands)

    not_evaluated: list[dict[str, str]] = []
    if not syntax_only_evaluated:
        not_evaluated.append(
            {
                "check": "syntax_only",
                "reason": "no Python syntax targets or syntax-only verifier commands were evaluated",
            }
        )
    if not command_execution_evaluated:
        not_evaluated.append(
            {
                "check": "command_execution",
                "reason": "no non-syntax runtime commands were executed",
            }
        )
    if not behavioral_requested:
        not_evaluated.append(
            {
                "check": "behavioral_verification",
                "reason": "no runtime stdout contract requested behavioral verification",
            }
        )
    elif not behavioral_evaluated:
        not_evaluated.append(
            {
                "check": "behavioral_verification",
                "reason": "behavioral verification was requested but no behavioral command result was recorded",
            }
        )

    overall_evidence_class = "not_evaluated"
    if behavioral_evaluated:
        overall_evidence_class = "behavioral_verification"
    elif command_execution_evaluated:
        overall_evidence_class = "command_execution"
    elif syntax_only_evaluated:
        overall_evidence_class = "syntax_only"

    evidence_summary = {
        "syntax_only": {
            "evaluated": syntax_only_evaluated,
            "checked_files": list(checked_files),
            "commands": syntax_only_commands,
        },
        "command_execution": {
            "evaluated": command_execution_evaluated,
            "commands": command_execution_commands,
        },
        "behavioral_verification": {
            "evaluated": behavioral_evaluated,
            "stdout_contract_requested": behavioral_requested,
            "json_assertion_count": behavioral_assertion_count,
            "commands": behavioral_commands,
        },
        "not_evaluated": not_evaluated,
    }
    return annotated_results, overall_evidence_class, evidence_summary


def _is_syntax_only_command(result: dict[str, Any]) -> bool:
    command_display = str(result.get("command_display") or result.get("command_text") or "").strip().lower()
    return command_display == "python -m compileall -q agent_output"


def _command_summary(result: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "command_id": str(result.get("command_id") or "").strip(),
        "command_display": str(result.get("command_display") or result.get("command_text") or "").strip(),
        "working_directory": str(result.get("working_directory") or ".").strip() or ".",
        "outcome": str(result.get("outcome") or "").strip(),
        "returncode": int(result.get("returncode", -1)),
    }
    failure_class = str(result.get("failure_class") or "").strip()
    if failure_class and failure_class != "none":
        summary["failure_class"] = failure_class
    stdout_contract_ok = result.get("stdout_contract_ok")
    if isinstance(stdout_contract_ok, bool):
        summary["stdout_contract_ok"] = stdout_contract_ok
    stdout_contract_error = str(result.get("stdout_contract_error") or "").strip()
    if stdout_contract_error:
        summary["stdout_contract_error"] = stdout_contract_error
    return summary


def runtime_verifier_evidence_classes() -> tuple[str, ...]:
    return _EVIDENCE_CLASSES
