from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


def _load_script_module(name: str, relative_path: str):
    path = Path(relative_path).resolve()
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_prompt_policy_summary_counts_from_turn_start_events() -> None:
    loop = _load_script_module(
        "run_live_acceptance_loop",
        "scripts/run_live_acceptance_loop.py",
    )

    events = [
        {
            "event": "turn_start",
            "data": {
                "resolver_policy": "resolver_v1",
                "selection_policy": "stable",
                "role_status": "stable",
                "dialect_status": "stable",
            },
        },
        {
            "event": "turn_start",
            "data": {
                "resolver_policy": "compiler",
                "selection_policy": "exact",
                "role_status": "candidate",
                "dialect_status": "stable",
            },
        },
        {"event": "turn_complete", "data": {}},
    ]

    summary = loop._prompt_policy_summary(events)
    assert summary["turn_start_count"] == 2
    assert summary["resolver_policy_counts"]["resolver_v1"] == 1
    assert summary["resolver_policy_counts"]["compiler"] == 1
    assert summary["selection_policy_counts"]["stable"] == 1
    assert summary["selection_policy_counts"]["exact"] == 1
    assert summary["role_status_counts"]["candidate"] == 1
    assert summary["dialect_status_counts"]["stable"] == 2


def test_runtime_failure_breakdown_count_from_events() -> None:
    loop = _load_script_module(
        "run_live_acceptance_loop_breakdown",
        "scripts/run_live_acceptance_loop.py",
    )
    events = [
        {"event": "runtime_verifier_completed", "data": {"failure_breakdown": {"timeout": 2, "command_failed": 1}}},
        {"event": "runtime_verifier_completed", "data": {"failure_breakdown": {"timeout": 1}}},
        {"event": "runtime_verifier_completed", "data": {"failure_breakdown": {"python_compile": 3}}},
    ]
    assert loop._runtime_failure_breakdown_count(events, "timeout") == 3
    assert loop._runtime_failure_breakdown_count(events, "command_failed") == 1
    assert loop._runtime_failure_breakdown_count(events, "python_compile") == 3


def test_turn_non_progress_rule_counts_from_events() -> None:
    loop = _load_script_module(
        "run_live_acceptance_loop_rule_counts",
        "scripts/run_live_acceptance_loop.py",
    )
    events = [
        {
            "event": "turn_non_progress",
            "data": {
                "contract_violations": [
                    {
                        "reason": "security_scope_contract_not_met",
                        "violations": [
                            {"rule_id": "SECURITY.PATH_TRAVERSAL"},
                            {"rule_id": "SECURITY.PATH_TRAVERSAL"},
                        ],
                    }
                ]
            },
        },
        {
            "event": "turn_non_progress",
            "data": {
                "contract_violations": [
                    {
                        "reason": "hallucination_scope_contract_not_met",
                        "violations": [
                            {"rule_id": "HALLUCINATION.INVENTED_DETAIL"},
                        ],
                    }
                ]
            },
        },
    ]
    counts = loop._turn_non_progress_rule_counts(events)
    assert counts["SECURITY.PATH_TRAVERSAL"] == 2
    assert counts["HALLUCINATION.INVENTED_DETAIL"] == 1


def test_runtime_event_schema_counts_from_events() -> None:
    loop = _load_script_module(
        "run_live_acceptance_loop_runtime_event_schema",
        "scripts/run_live_acceptance_loop.py",
    )
    events = [
        {"event": "turn_start", "data": {"runtime_event": {"schema_version": "v1"}}},
        {"event": "turn_complete", "data": {"runtime_event": {"schema_version": "v1"}}},
        {"event": "turn_failed", "data": {"runtime_event": {"schema_version": "v0"}}},
        {"event": "turn_failed", "data": {}},
    ]
    assert loop._runtime_event_presence_count(events) == 3
    assert loop._runtime_event_schema_version_count(events, "v1") == 2
    assert loop._runtime_event_schema_version_count(events, "v0") == 1


def test_guard_terminal_reason_count_from_events() -> None:
    loop = _load_script_module(
        "run_live_acceptance_loop_guard_reason",
        "scripts/run_live_acceptance_loop.py",
    )
    events = [
        {
            "event": "guard_terminal_failure",
            "data": {"guard_decision": {"terminal_reason": {"code": "HALLUCINATION_PERSISTENT"}}},
        },
        {
            "event": "guard_terminal_failure",
            "data": {"guard_decision": {"terminal_reason": {"code": "GUARD_RETRY_EXCEEDED"}}},
        },
    ]
    assert loop._guard_terminal_reason_count(events, "HALLUCINATION_PERSISTENT") == 1


def test_report_live_acceptance_patterns_includes_prompt_policy_counters() -> None:
    reporter = _load_script_module(
        "report_live_acceptance_patterns",
        "scripts/report_live_acceptance_patterns.py",
    )

    runs = [
        {
            "model": "m1",
            "iteration": 1,
            "passed": True,
            "session_status": "done",
            "metrics": {
                "prompt_turn_start_total": 4,
                "prompt_resolver_policy_compiler": 0,
                "prompt_resolver_policy_resolver_v1": 4,
                "prompt_selection_policy_stable": 4,
                "prompt_selection_policy_canary": 0,
                "prompt_selection_policy_exact": 0,
                "runtime_event_envelope_count": 7,
                "runtime_event_schema_v1_count": 7,
                "runtime_verifier_failure_python_compile": 1,
                "runtime_verifier_failure_timeout": 0,
                "runtime_verifier_failure_command_failed": 0,
                "runtime_verifier_failure_missing_runtime": 0,
                "runtime_verifier_failure_deployment_missing": 0,
                "guard_retry_scheduled": 0,
                "guard_terminal_failure": 0,
                "guard_terminal_reason_hallucination_persistent": 0,
                "turn_non_progress_hallucination_scope": 0,
                "turn_non_progress_security_scope": 0,
                "turn_non_progress_consistency_scope": 0,
                "turn_non_progress_rule_counts": {
                    "HALLUCINATION.INVENTED_DETAIL": 0,
                    "SECURITY.PATH_TRAVERSAL": 0,
                },
            },
            "db_summary": {"issue_statuses": {"REQ-1": "done", "ARC-1": "done", "COD-1": "done", "REV-1": "done"}},
            "chain_complete": True,
        },
        {
            "model": "m2",
            "iteration": 1,
            "passed": False,
            "session_status": "terminal_failure",
            "metrics": {
                "prompt_turn_start_total": 2,
                "prompt_resolver_policy_compiler": 2,
                "prompt_resolver_policy_resolver_v1": 0,
                "prompt_selection_policy_stable": 0,
                "prompt_selection_policy_canary": 1,
                "prompt_selection_policy_exact": 1,
                "runtime_event_envelope_count": 5,
                "runtime_event_schema_v1_count": 5,
                "runtime_verifier_failure_python_compile": 0,
                "runtime_verifier_failure_timeout": 1,
                "runtime_verifier_failure_command_failed": 1,
                "runtime_verifier_failure_missing_runtime": 0,
                "runtime_verifier_failure_deployment_missing": 1,
                "guard_retry_scheduled": 2,
                "guard_terminal_failure": 1,
                "guard_terminal_reason_hallucination_persistent": 1,
                "turn_non_progress_hallucination_scope": 1,
                "turn_non_progress_security_scope": 2,
                "turn_non_progress_consistency_scope": 3,
                "turn_non_progress_rule_counts": {
                    "HALLUCINATION.INVENTED_DETAIL": 1,
                    "SECURITY.PATH_TRAVERSAL": 2,
                },
            },
            "db_summary": {"issue_statuses": {"REQ-1": "done", "ARC-1": "blocked"}},
            "chain_complete": False,
        },
    ]

    report = reporter._build_report("batch-1", runs)
    counters = report["pattern_counters"]
    assert counters["prompt_turn_start_total"] == 6
    assert counters["prompt_resolver_policy_compiler"] == 2
    assert counters["prompt_resolver_policy_resolver_v1"] == 4
    assert counters["prompt_selection_policy_stable"] == 4
    assert counters["prompt_selection_policy_canary"] == 1
    assert counters["prompt_selection_policy_exact"] == 1
    assert counters["runtime_event_envelope_count"] == 12
    assert counters["runtime_event_schema_v1_count"] == 12
    assert counters["runtime_verifier_failure_python_compile"] == 1
    assert counters["runtime_verifier_failure_timeout"] == 1
    assert counters["runtime_verifier_failure_command_failed"] == 1
    assert counters["runtime_verifier_failure_missing_runtime"] == 0
    assert counters["runtime_verifier_failure_deployment_missing"] == 1
    assert counters["guard_retry_scheduled"] == 2
    assert counters["guard_terminal_failure"] == 1
    assert counters["guard_terminal_reason_hallucination_persistent"] == 1
    assert counters["turn_non_progress_hallucination_scope"] == 1
    assert counters["turn_non_progress_security_scope"] == 2
    assert counters["turn_non_progress_consistency_scope"] == 3
    rule_counts = report["guard_rule_violation_counts"]
    assert rule_counts["HALLUCINATION.INVENTED_DETAIL"] == 1
    assert rule_counts["SECURITY.PATH_TRAVERSAL"] == 2
    assert report["schema_health"]["runtime_event_schema_v1_coverage"] == 1.0
    compliance = report["model_compliance"]
    assert "m1" in compliance
    assert "m2" in compliance
    assert compliance["m1"]["guard_pass_rate"] == 1.0
    assert compliance["m2"]["terminal_failure_rate"] == 1.0
    assert compliance["m2"]["compliance_score"] < compliance["m1"]["compliance_score"]


def test_report_live_acceptance_patterns_loads_monolith_matrix_summary(tmp_path: Path) -> None:
    reporter = _load_script_module(
        "report_live_acceptance_patterns_matrix",
        "scripts/report_live_acceptance_patterns.py",
    )
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "execute_mode": True,
                "recommended_default_builder_variant": "architect",
                "entries": [{"builder_variant": "architect"}],
            }
        ),
        encoding="utf-8",
    )
    summary = reporter._load_matrix_summary(matrix_path)
    assert summary["execute_mode"] is True
    assert summary["recommended_default_builder_variant"] == "architect"
    assert summary["entry_count"] == 1
