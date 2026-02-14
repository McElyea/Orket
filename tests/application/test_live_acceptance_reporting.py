from __future__ import annotations

import importlib.util
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
                "runtime_verifier_failure_python_compile": 1,
                "runtime_verifier_failure_timeout": 0,
                "runtime_verifier_failure_command_failed": 0,
                "runtime_verifier_failure_missing_runtime": 0,
                "runtime_verifier_failure_deployment_missing": 0,
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
                "runtime_verifier_failure_python_compile": 0,
                "runtime_verifier_failure_timeout": 1,
                "runtime_verifier_failure_command_failed": 1,
                "runtime_verifier_failure_missing_runtime": 0,
                "runtime_verifier_failure_deployment_missing": 1,
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
    assert counters["runtime_verifier_failure_python_compile"] == 1
    assert counters["runtime_verifier_failure_timeout"] == 1
    assert counters["runtime_verifier_failure_command_failed"] == 1
    assert counters["runtime_verifier_failure_missing_runtime"] == 0
    assert counters["runtime_verifier_failure_deployment_missing"] == 1
