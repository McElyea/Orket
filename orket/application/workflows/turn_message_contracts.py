"""Render the existing artifact, scenario and runtime-verifier prompt contracts."""
from __future__ import annotations

import json
from typing import Any

from orket.runtime.config.turn_prompt_contracts import runtime_verifier_prompt_enabled

from .turn_artifact_destination import TurnArtifactDestination
from .turn_artifact_semantic_prompt_hints import artifact_semantic_exact_shape_hints


def append_artifact_contract(messages: list[dict[str, str]], context: dict[str, Any], artifact_contract: Any) -> None:
    profile_traits = context.get("profile_traits")
    profile_traits = dict(profile_traits) if isinstance(profile_traits, dict) else {}
    artifact_contract_allowed = bool(profile_traits.get("artifact_contract_required", True))
    if (
        artifact_contract_allowed
        and isinstance(artifact_contract, dict)
        and artifact_contract
        and (str(artifact_contract.get("kind") or "").strip().lower() != "none")
    ):
        messages.append(
            {"role": "user", "content": "Artifact Contract JSON:\n" + json.dumps(artifact_contract, sort_keys=True)}
        )
        semantic_checks = artifact_contract.get("semantic_checks")
        if isinstance(semantic_checks, list) and semantic_checks:
            semantic_lines = [
                "- Additional semantic checks apply to written artifact paths.",
                "- Every listed Must contain token is checked as an exact substring; include each one verbatim in the final file content.",
                "- Every listed Must not contain token is also checked as an exact substring; remove each one verbatim from the final file content.",
            ]
            exact_shape_hints: list[str] = []
            seen_exact_shape_hints: set[str] = set()
            for raw_check in semantic_checks:
                if not isinstance(raw_check, dict):
                    continue
                path = str(raw_check.get("path") or "").strip()
                label = str(raw_check.get("label") or "").strip()
                if path:
                    semantic_lines.append(f"- Path: {path}")
                if label:
                    semantic_lines.append(f"  - Purpose: {label}")
                must_contain = [
                    str(token).strip() for token in raw_check.get("must_contain") or [] if str(token).strip()
                ]
                if must_contain:
                    semantic_lines.append("  - Must contain: " + ", ".join(must_contain))
                must_not_contain = [
                    str(token).strip() for token in raw_check.get("must_not_contain") or [] if str(token).strip()
                ]
                if must_not_contain:
                    semantic_lines.append("  - Must not contain: " + ", ".join(must_not_contain))
                for hint in artifact_semantic_exact_shape_hints(
                    path=path, must_contain=must_contain, must_not_contain=must_not_contain
                ):
                    if hint in seen_exact_shape_hints:
                        continue
                    seen_exact_shape_hints.add(hint)
                    exact_shape_hints.append(hint)
            messages.append({"role": "user", "content": "Artifact Semantic Contract:\n" + "\n".join(semantic_lines)})
            if exact_shape_hints:
                messages.append(
                    {"role": "user", "content": "Artifact Exact-Shape Hints:\n" + "\n".join(exact_shape_hints)}
                )


def append_scenario_contract(
    messages: list[dict[str, str]], context: dict[str, Any], destination: TurnArtifactDestination
) -> None:
    scenario_truth = context.get("scenario_truth")
    if isinstance(scenario_truth, dict) and scenario_truth:
        raw_blocked_issue_policy = scenario_truth.get("blocked_issue_policy")
        blocked_issue_policy: dict[str, Any] = (
            {str(key): value for key, value in raw_blocked_issue_policy.items()}
            if isinstance(raw_blocked_issue_policy, dict)
            else {}
        )
        allowed_issue_ids = [
            str(token).strip() for token in blocked_issue_policy.get("allowed_issue_ids") or [] if str(token).strip()
        ]
        scenario_lines = [
            f"- scenario_id: {str(scenario_truth.get('scenario_id') or '').strip()}",
            "- blocked_issue_policy.allowed_issue_ids: "
            + (", ".join(allowed_issue_ids) if allowed_issue_ids else "none"),
            "- blocked_issue_policy.blocked_implies_run_failure: "
            + str(bool(blocked_issue_policy.get("blocked_implies_run_failure"))).lower(),
        ]
        expected_terminal_status = str(scenario_truth.get("expected_terminal_status") or "").strip()
        if expected_terminal_status:
            scenario_lines.append(f"- expected_terminal_status: {expected_terminal_status}")
        expected_truth_classification = str(scenario_truth.get("expected_truth_classification") or "").strip()
        if expected_truth_classification:
            scenario_lines.append(f"- expected_truth_classification: {expected_truth_classification}")
        if destination.issue_id in allowed_issue_ids:
            scenario_lines.append("- This issue is one of the admitted blocked_issue_policy.allowed_issue_ids.")
        messages.append({"role": "user", "content": "Scenario Truth Contract:\n" + "\n".join(scenario_lines)})


def append_verifier_contract(messages: list[dict[str, str]], context: dict[str, Any], artifact_contract: Any) -> None:
    runtime_verifier_contract = context.get("runtime_verifier_contract")
    runtime_verifier_contract = dict(runtime_verifier_contract) if isinstance(runtime_verifier_contract, dict) else {}
    if runtime_verifier_prompt_enabled(context):
        entrypoint_path = str(artifact_contract.get("entrypoint_path") or "").strip()
        artifact_kind = str(artifact_contract.get("kind") or "").strip().lower()
        verifier_lines: list[str] = []
        explicit_commands = runtime_verifier_contract.get("commands")
        if isinstance(explicit_commands, list) and explicit_commands:
            verifier_lines.append("- The runtime verifier will execute these commands exactly:")
            for raw_command in explicit_commands:
                cwd = "."
                argv = raw_command
                if isinstance(raw_command, dict):
                    cwd = str(raw_command.get("cwd") or ".").strip() or "."
                    argv = raw_command.get("argv")
                if not isinstance(argv, list):
                    continue
                rendered = " ".join(str(token).strip() for token in argv if str(token).strip())
                if not rendered:
                    continue
                verifier_lines.append(f"  - cwd={cwd}: {rendered}")
        elif artifact_kind == "app" and entrypoint_path:
            verifier_lines.append(f"- The runtime verifier will execute exactly: python {entrypoint_path}")
            verifier_lines.append("- The entrypoint must succeed with no positional arguments or interactive input.")
            verifier_lines.append(
                "- The entrypoint runs as a script, so do not use package-relative imports in that file."
            )
        if bool(runtime_verifier_contract.get("expect_json_stdout", False)):
            verifier_lines.append("- The verifier command checked for stdout must print valid JSON.")
        json_assertions = runtime_verifier_contract.get("json_assertions")
        if isinstance(json_assertions, list) and json_assertions:
            verifier_lines.append("- Required stdout assertions:")
            for assertion in json_assertions:
                if not isinstance(assertion, dict):
                    continue
                path = str(assertion.get("path") or "").strip()
                op = str(assertion.get("op") or "").strip()
                value = assertion.get("value")
                if not path or not op:
                    continue
                verifier_lines.append(f"  - {path} {op} {value!r}")
        if verifier_lines:
            messages.append({"role": "user", "content": "Runtime Verifier Contract:\n" + "\n".join(verifier_lines)})
