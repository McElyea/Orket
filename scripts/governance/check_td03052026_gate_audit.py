from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger


GATE_IDS = ("G1", "G2", "G3", "G4", "G5", "G6", "G7")
READINESS_PREREQS = ("G1", "G2", "G3", "G4", "G5")
REQUIRED_CI_SNIPPETS = {
    "G1": "python scripts/governance/check_install_surface_convergence.py",
    "G2": "python -m pytest -q tests/interfaces/test_server_launcher.py",
    "G3": "python -m pytest -q tests/interfaces/test_api_lifecycle_subscribers.py",
    "G4": "python -m pytest -q tests/application/test_orchestrator_epic.py -k closes_provider_per_turn_across_repeated_cycles",
    "G5": "python -m pytest -q tests/runtime/test_logging_isolation.py",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit TD03052026 gate enforcement and readiness artifact integrity.")
    parser.add_argument(
        "--dashboard",
        default="benchmarks/results/techdebt/td03052026/hardening_dashboard.json",
        help="Gate dashboard JSON path.",
    )
    parser.add_argument(
        "--quality-workflow",
        default=".gitea/workflows/quality.yml",
        help="Quality workflow path.",
    )
    parser.add_argument(
        "--out",
        default="benchmarks/results/techdebt/td03052026/readiness_checklist.json",
        help="Audit output JSON path.",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Require G1-G5 to be green.",
    )
    return parser


def _load_json(path: Path, failures: list[str], *, label: str) -> dict[str, Any]:
    if not path.exists():
        failures.append(f"missing {label}: {path.as_posix()}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        failures.append(f"unable to parse {label} JSON: {path.as_posix()}")
        return {}
    if not isinstance(payload, dict):
        failures.append(f"{label} root must be JSON object: {path.as_posix()}")
        return {}
    return payload


def _assert_ci_snippets(workflow_path: Path, failures: list[str]) -> list[dict[str, Any]]:
    assertions: list[dict[str, Any]] = []
    if not workflow_path.exists():
        failures.append(f"missing quality workflow: {workflow_path.as_posix()}")
        return assertions
    text = workflow_path.read_text(encoding="utf-8")
    for gate_id, snippet in REQUIRED_CI_SNIPPETS.items():
        present = snippet in text
        assertions.append(
            {
                "id": f"ci_enforces_{gate_id.lower()}",
                "passed": present,
                "detail": f"workflow={workflow_path.as_posix()} snippet={snippet}",
            }
        )
        if not present:
            failures.append(f"quality workflow missing {gate_id} snippet: {snippet}")
    return assertions


def _assert_gate_shape_and_evidence(
    dashboard_path: Path,
    dashboard: dict[str, Any],
    failures: list[str],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    assertions: list[dict[str, Any]] = []
    states: dict[str, str] = {}
    gates = dashboard.get("gates")
    if not isinstance(gates, dict):
        failures.append(f"dashboard missing gate map: {dashboard_path.as_posix()}")
        return assertions, states

    for gate_id in GATE_IDS:
        entry = gates.get(gate_id)
        if not isinstance(entry, dict):
            failures.append(f"dashboard missing gate entry: {gate_id}")
            continue
        state = str(entry.get("state") or "").strip().lower()
        states[gate_id] = state
        evidence = entry.get("evidence") if isinstance(entry.get("evidence"), list) else []
        updated = str(entry.get("updated_at_utc") or "").strip()
        passed = bool(state in {"green", "red", "waived"} and updated)
        assertions.append(
            {
                "id": f"gate_shape_{gate_id.lower()}",
                "passed": passed,
                "detail": f"state={state} evidence_count={len(evidence)} updated_at_utc_present={bool(updated)}",
            }
        )
        if not passed:
            failures.append(f"invalid gate shape for {gate_id}: state={state} updated_at_utc_present={bool(updated)}")
        if state == "green" and not evidence:
            failures.append(f"green gate missing evidence list: {gate_id}")

        result_paths = [Path(str(token)) for token in evidence if str(token).replace("\\", "/").endswith("/result.json")]
        for result_path in result_paths:
            result_payload = _load_json(result_path, failures, label=f"{gate_id} evidence result")
            if not result_payload:
                continue
            result_gate_id = str(result_payload.get("gate_id") or "").strip().upper()
            if result_gate_id != gate_id:
                failures.append(
                    f"gate evidence ID mismatch for {gate_id}: {result_path.as_posix()} gate_id={result_gate_id or '<missing>'}"
                )
    return assertions, states


def _assert_readiness(states: dict[str, str], failures: list[str], *, require_ready: bool) -> dict[str, Any]:
    prereq_green = all(states.get(gate_id) == "green" for gate_id in READINESS_PREREQS)
    if require_ready and not prereq_green:
        failures.append(
            "readiness prerequisite gates are not all green: "
            + ", ".join(f"{gate_id}={states.get(gate_id, '<missing>')}" for gate_id in READINESS_PREREQS)
        )
    return {
        "id": "readiness_prerequisites_g1_to_g5_green",
        "passed": prereq_green,
        "detail": ", ".join(f"{gate_id}={states.get(gate_id, '<missing>')}" for gate_id in READINESS_PREREQS),
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    failures: list[str] = []
    assertions: list[dict[str, Any]] = []

    dashboard_path = Path(str(args.dashboard))
    workflow_path = Path(str(args.quality_workflow))
    out_path = Path(str(args.out))

    dashboard = _load_json(dashboard_path, failures, label="dashboard")
    gate_assertions, states = _assert_gate_shape_and_evidence(dashboard_path, dashboard, failures)
    assertions.extend(gate_assertions)
    assertions.extend(_assert_ci_snippets(workflow_path, failures))
    assertions.append(_assert_readiness(states, failures, require_ready=bool(args.require_ready)))

    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema_version": "td03052026.readiness_audit.v1",
        "status": status,
        "dashboard_path": dashboard_path.resolve().as_posix(),
        "quality_workflow_path": workflow_path.resolve().as_posix(),
        "gate_states": states,
        "assertions": assertions,
        "failures": failures,
    }
    write_payload_with_diff_ledger(out_path, payload)

    if status == "PASS":
        print("TD03052026 gate audit passed.")
        return 0

    print("TD03052026 gate audit failed:")
    for failure in failures:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
