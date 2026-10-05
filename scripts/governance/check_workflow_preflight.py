"""Structural workflow readiness; no inference and no claim of accepted work."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pydantic import ValidationError

from orket.application.services import orchestrator_team_policy as team_policy
from orket.application.services.card_completion_service import declared_card_acceptance
from orket.application.services.toolbox import ToolBox, get_tool_map
from orket.application.workflows.orchestrator_epic_workflow import preflight_epic_team
from orket.core.domain.records import IssueRecord
from orket.exceptions import CardNotFound, ExecutionFailed
from orket.runtime.config.config_loader import ConfigLoader
from orket.schema import EpicConfig, RoleConfig, TeamConfig
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger


def inspect_workflow(root: Path, name: str, department: str = "core") -> dict:
    loader = ConfigLoader(root, department)
    org = loader.load_organization()
    epic = loader.load_asset("epics", name, EpicConfig)
    team = loader.load_asset("teams", epic.team, TeamConfig)
    errors = []
    threshold = team_policy.small_project_issue_threshold(org)
    def policy():
        return team_policy.project_team_policy(team, issue_count=len(epic.issues), threshold=threshold,
            active=0 < len(epic.issues) <= threshold, variant="coder")
    try:
        preflight_epic_team(epic, team, "structural-preflight", select_team=policy,
            should_inject=lambda: team_policy.should_auto_inject_small_project_reviewer(org),
            inject_reviewer=lambda: team_policy.auto_inject_small_project_reviewer_seat(org, team),
            emit=lambda *_: None)
    except ExecutionFailed as exc:
        errors.append(str(exc))
    if not epic.issues:
        errors.append("No cards declared")
    toolbox = ToolBox({}, str(root / "workspace"), [], organization=org, decision_nodes=loader.decision_nodes)
    available = set(get_tool_map(toolbox))
    for issue in epic.issues:
        try:
            record = IssueRecord(id=issue.id, seat=issue.seat, summary=issue.name, params=issue.params)
            if declared_card_acceptance(record) is None:
                errors.append(f"{issue.id}: missing completion_acceptance")
        except ValidationError as exc:
            errors.append(f"{issue.id}: invalid completion_acceptance: {exc}")
        if issue.seat not in team.seats:
            errors.append(f"{issue.id}: missing declared seat {issue.seat}")
    for seat, config in team.seats.items():
        for role in config.roles:
            try:
                asset = loader.load_asset("roles", role, RoleConfig)
                unknown = sorted(set(asset.tools) - available)
                if unknown:
                    errors.append(f"{seat}/{role}: unavailable tools {unknown}")
            except (CardNotFound, ValidationError) as exc:
                errors.append(f"{seat}/{role}: {exc}")
    return {"epic": name, "proof_mode": "structural", "ready": not errors, "errors": errors,
            "scope": "All declared seats/tools and acceptance syntax; no inference, reachability or behavior proof"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--epic", action="append", required=True)
    parser.add_argument("--department", default="core")
    parser.add_argument("--out", type=Path, default=Path("benchmarks/staging/General/workflow_preflight.json"))
    args = parser.parse_args()
    results = []
    for name in args.epic:
        try:
            results.append(inspect_workflow(args.project.resolve(), name, args.department))
        except (CardNotFound, ValidationError, ValueError, OSError) as exc:
            results.append({"epic": name, "ready": False, "errors": [f"{type(exc).__name__}: {exc}"]})
    payload = {"proof_mode": "structural", "workflows": results, "ready": all(row["ready"] for row in results)}
    write_payload_with_diff_ledger(args.out, payload)
    print(json.dumps(payload))
    return 0 if payload["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
