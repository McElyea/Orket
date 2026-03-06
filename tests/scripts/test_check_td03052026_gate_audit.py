from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_td03052026_gate_audit import GATE_IDS
from scripts.governance.check_td03052026_gate_audit import REQUIRED_CI_SNIPPETS
from scripts.governance.check_td03052026_gate_audit import main


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _gate_entry(state: str, evidence: list[str]) -> dict:
    return {
        "state": state,
        "detail": f"{state} detail",
        "evidence": evidence,
        "updated_at_utc": "2026-03-05T00:00:00Z",
    }


def _seed_dashboard(tmp_path: Path, *, missing_gate: str = "") -> tuple[Path, dict]:
    gates: dict[str, dict] = {}
    for gate_id in GATE_IDS:
        if gate_id == missing_gate:
            continue
        state = "green" if gate_id in {"G1", "G2", "G3", "G4", "G5", "G6"} else "red"
        evidence: list[str] = []
        if state == "green":
            result_path = tmp_path / "evidence" / gate_id.lower() / "result.json"
            _write(result_path, json.dumps({"gate_id": gate_id}))
            evidence = [result_path.resolve().as_posix()]
        gates[gate_id] = _gate_entry(state=state, evidence=evidence)

    dashboard = {
        "schema_version": "td03052026.hardening_dashboard.v1",
        "updated_at_utc": "2026-03-05T00:00:00Z",
        "gates": gates,
    }
    dashboard_path = tmp_path / "hardening_dashboard.json"
    _write(dashboard_path, json.dumps(dashboard))
    return dashboard_path, dashboard


def _seed_quality_workflow(tmp_path: Path, *, omit_gate: str = "") -> Path:
    lines = ["name: Quality", "jobs:", "  architecture_gates:", "    steps:"]
    for gate_id, snippet in REQUIRED_CI_SNIPPETS.items():
        if gate_id == omit_gate:
            continue
        lines.append(f"      - run: |\n          {snippet}")
    workflow_path = tmp_path / "quality.yml"
    _write(workflow_path, "\n".join(lines) + "\n")
    return workflow_path


def test_td03052026_gate_audit_passes_when_dashboard_and_ci_are_aligned(tmp_path: Path) -> None:
    dashboard_path, _ = _seed_dashboard(tmp_path)
    workflow_path = _seed_quality_workflow(tmp_path)
    out_path = tmp_path / "readiness.json"

    exit_code = main(
        [
            "--dashboard",
            str(dashboard_path),
            "--quality-workflow",
            str(workflow_path),
            "--out",
            str(out_path),
            "--require-ready",
        ]
    )
    assert exit_code == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert "diff_ledger" in payload


def test_td03052026_gate_audit_fails_when_dashboard_gate_missing(tmp_path: Path) -> None:
    dashboard_path, _ = _seed_dashboard(tmp_path, missing_gate="G3")
    workflow_path = _seed_quality_workflow(tmp_path)
    out_path = tmp_path / "readiness.json"

    exit_code = main(
        [
            "--dashboard",
            str(dashboard_path),
            "--quality-workflow",
            str(workflow_path),
            "--out",
            str(out_path),
        ]
    )
    assert exit_code == 1


def test_td03052026_gate_audit_fails_when_ci_snippet_missing(tmp_path: Path) -> None:
    dashboard_path, _ = _seed_dashboard(tmp_path)
    workflow_path = _seed_quality_workflow(tmp_path, omit_gate="G5")
    out_path = tmp_path / "readiness.json"

    exit_code = main(
        [
            "--dashboard",
            str(dashboard_path),
            "--quality-workflow",
            str(workflow_path),
            "--out",
            str(out_path),
        ]
    )
    assert exit_code == 1
