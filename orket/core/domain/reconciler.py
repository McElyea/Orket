"""Deterministic reconciliation plans over immutable, explicitly supplied assets."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StructuralAsset:
    department: str
    kind: str
    name: str
    content: str

    @property
    def relative_path(self) -> str:
        return f"{self.department}/{self.kind}/{self.name}.json"


@dataclass(frozen=True)
class ReconciliationWrite:
    relative_path: str
    expected_content: str
    content: str


@dataclass(frozen=True)
class ReconciliationAdoption:
    kind: str
    name: str
    department: str
    target_id: str
    target_path: str


@dataclass(frozen=True)
class ReconciliationProblem:
    relative_path: str
    detail: str


@dataclass(frozen=True)
class ReconciliationPlan:
    writes: tuple[ReconciliationWrite, ...] = ()
    adoptions: tuple[ReconciliationAdoption, ...] = ()
    problems: tuple[ReconciliationProblem, ...] = ()


def _read_assets(assets: tuple[StructuralAsset, ...]) -> tuple[dict, list[ReconciliationProblem]]:
    records, problems = {}, []
    for asset in sorted(assets, key=lambda a: a.relative_path):
        try:
            if asset.relative_path in records:
                raise ValueError("Duplicate asset path")
            if asset.kind not in {"rocks", "epics", "issues"}:
                raise ValueError("Unknown structural asset kind")
            payload = json.loads(asset.content)
            if not isinstance(payload, dict):
                raise ValueError("Structural asset must be a JSON object")
            records[asset.relative_path] = asset, payload
        except (ValueError, TypeError) as exc:
            problems.append(ReconciliationProblem(asset.relative_path, str(exc)))
    return records, problems


def _linked_names(records: dict) -> tuple[set[str], set[str], list[ReconciliationProblem]]:
    epics, issues, problems = set(), set(), []
    for path, (asset, payload) in records.items():
        try:
            if asset.kind == "rocks":
                references = payload.get("epics", [])
                if not isinstance(references, list):
                    raise ValueError("Rock epics must be a list")
                for reference in references:
                    if not isinstance(reference, dict) or not isinstance(reference.get("epic"), str):
                        raise ValueError("Rock epic reference requires an epic name")
                    epics.add(reference["epic"])
            elif asset.kind == "epics":
                references = payload.get("issues") or payload.get("stories") or []
                if not isinstance(references, list):
                    raise ValueError("Epic issues must be a list")
                for reference in references:
                    if not isinstance(reference, dict):
                        raise ValueError("Epic issue reference must be an object")
                    name = reference.get("id") or reference.get("name") or reference.get("summary")
                    if name is not None:
                        if not isinstance(name, str):
                            raise ValueError("Epic issue identity must be a string")
                        issues.add(name)
        except (ValueError, TypeError) as exc:
            problems.append(ReconciliationProblem(path, str(exc)))
    return epics, issues, problems


def _adopt(
    records: dict,
    orphans: list[tuple[StructuralAsset, dict[str, Any]]],
    *,
    target_path: str,
    target_id: str,
    field: str,
) -> ReconciliationPlan:
    if not orphans:
        return ReconciliationPlan()
    if target_path not in records:
        return ReconciliationPlan(problems=(ReconciliationProblem(target_path, "Missing orphan adoption target"),))
    target, payload = records[target_path]
    entries = payload.setdefault(field, [])
    if not isinstance(entries, list):
        return ReconciliationPlan(problems=(ReconciliationProblem(target_path, f"Target {field} must be a list"),))
    adoptions = []
    for asset, content in orphans:
        entries.append({"epic": asset.name, "department": asset.department} if field == "epics" else content)
        adoptions.append(ReconciliationAdoption(asset.kind, asset.name, asset.department, target_id, target_path))
    write = ReconciliationWrite(target_path, target.content, json.dumps(payload, indent=2) + "\n")
    return ReconciliationPlan(writes=(write,), adoptions=tuple(adoptions))


class StructuralReconciler:
    """Compute proposed updates only; application services own traversal and writes."""

    @staticmethod
    def plan(
        assets: tuple[StructuralAsset, ...],
        *,
        default_rock_id: str = "run_the_business",
        default_epic_id: str = "unplanned_support",
    ) -> ReconciliationPlan:
        records, problems = _read_assets(assets)
        linked_epics, linked_issues, reference_problems = _linked_names(records)
        problems.extend(reference_problems)
        if problems:
            return ReconciliationPlan(problems=tuple(problems))
        epics = []
        for asset, payload in records.values():
            if asset.kind == "epics" and asset.name != default_epic_id and asset.name not in linked_epics:
                epics.append((asset, payload))
                linked_epics.add(asset.name)
        issues = [(a, p) for a, p in records.values() if a.kind == "issues" and a.name not in linked_issues]
        epic_plan = _adopt(
            records, epics, target_path=f"core/rocks/{default_rock_id}.json", target_id=default_rock_id, field="epics"
        )
        issue_plan = _adopt(
            records, issues, target_path=f"core/epics/{default_epic_id}.json", target_id=default_epic_id, field="issues"
        )
        if epic_plan.problems or issue_plan.problems:
            return ReconciliationPlan(problems=epic_plan.problems + issue_plan.problems)
        return ReconciliationPlan(epic_plan.writes + issue_plan.writes, epic_plan.adoptions + issue_plan.adoptions)
