import json
from pathlib import Path
from typing import List, Dict, Any
from orket.logging import log_event


class StructuralReconciler:
    """
    Ensures structural integrity of the project board.
    Finds orphans and adopts them into 'Run the Business' or 'unplanned support'.
    """

    def __init__(self, root_path: Path = Path("model")):
        # Resolve against repo cwd once, so reads stay stable across temp workspace runs.
        self.root_path = root_path.resolve()
        self.default_rock_id = "run_the_business"
        self.default_epic_id = "unplanned_support"

    def reconcile_all(self):
        """Runs the full reconciliation sweep across all departments."""
        log_event("reconciler_start", {"root_path": str(self.root_path)}, workspace=Path("workspace/default"))

        # 1. Gather all linked assets to identify orphans
        linked_epics = set()
        linked_issues = set()

        # Scan Rocks for linked Epics
        for dept_dir in self.root_path.iterdir():
            if not dept_dir.is_dir():
                continue
            rock_path = dept_dir / "rocks"
            if rock_path.exists():
                for rf in rock_path.glob("*.json"):
                    try:
                        data = json.loads(rf.read_text(encoding="utf-8"))
                        for epic_ref in data.get("epics", []):
                            linked_epics.add(epic_ref["epic"])
                    except (json.JSONDecodeError, OSError, KeyError) as e:
                        log_event(
                            "reconciler_rock_parse_failed",
                            {"file": rf.name, "error": str(e)},
                            workspace=Path("workspace/default"),
                        )
                        continue

        # Scan Epics for linked Issues
        for dept_dir in self.root_path.iterdir():
            if not dept_dir.is_dir():
                continue
            epic_path = dept_dir / "epics"
            if epic_path.exists():
                for ef in epic_path.glob("*.json"):
                    try:
                        data = json.loads(ef.read_text(encoding="utf-8"))
                        for issue in data.get("issues", []) or data.get("stories", []):
                            linked_issues.add(issue.get("id") or issue.get("name") or issue.get("summary"))
                    except (json.JSONDecodeError, OSError, KeyError) as e:
                        log_event(
                            "reconciler_epic_parse_failed",
                            {"file": ef.name, "error": str(e)},
                            workspace=Path("workspace/default"),
                        )
                        continue

        # 2. Adopt orphaned Epics into 'Run the Business'
        self._adopt_epics(linked_epics)

        # 3. Adopt orphaned Issues into 'unplanned support'
        self._adopt_issues(linked_issues)

    def _adopt_epics(self, linked_epics: set):
        rtb_path = self.root_path / "core" / "rocks" / f"{self.default_rock_id}.json"
        if not rtb_path.exists():
            return

        rtb_data = json.loads(rtb_path.read_text(encoding="utf-8"))
        dirty = False

        for dept_dir in self.root_path.iterdir():
            if not dept_dir.is_dir():
                continue
            epic_path = dept_dir / "epics"
            if epic_path.exists():
                for ef in epic_path.glob("*.json"):
                    epic_id = ef.stem
                    if epic_id == self.default_epic_id:
                        continue

                    if epic_id not in linked_epics:
                        log_event(
                            "reconciler_orphan_epic_adopted",
                            {
                                "epic_id": epic_id,
                                "department": dept_dir.name,
                                "target_rock": self.default_rock_id,
                            },
                            workspace=Path("workspace/default"),
                        )
                        rtb_data.setdefault("epics", []).append({
                            "epic": epic_id,
                            "department": dept_dir.name,
                        })
                        linked_epics.add(epic_id)
                        dirty = True

        if dirty:
            rtb_path.write_text(json.dumps(rtb_data, indent=2) + "\n", encoding="utf-8")

    def _adopt_issues(self, linked_issues: set):
        ups_path = self.root_path / "core" / "epics" / f"{self.default_epic_id}.json"
        if not ups_path.exists():
            return

        ups_data = json.loads(ups_path.read_text(encoding="utf-8"))
        dirty = False

        for dept_dir in self.root_path.iterdir():
            if not dept_dir.is_dir():
                continue
            issue_dir = dept_dir / "issues"
            if issue_dir.exists():
                for isf in issue_dir.glob("*.json"):
                    issue_id = isf.stem
                    if issue_id not in linked_issues:
                        log_event(
                            "reconciler_orphan_issue_adopted",
                            {
                                "issue_id": issue_id,
                                "department": dept_dir.name,
                                "target_epic": self.default_epic_id,
                            },
                            workspace=Path("workspace/default"),
                        )
                        try:
                            issue_data = json.loads(isf.read_text(encoding="utf-8"))
                            ups_data.setdefault("issues", []).append(issue_data)
                            dirty = True
                        except (json.JSONDecodeError, OSError, KeyError) as e:
                            log_event(
                                "reconciler_issue_parse_failed",
                                {"file": isf.name, "error": str(e)},
                                workspace=Path("workspace/default"),
                            )
                            continue

        if dirty:
            ups_path.write_text(json.dumps(ups_data, indent=2) + "\n", encoding="utf-8")
