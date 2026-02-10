import json
from pathlib import Path
from typing import List, Dict, Any
from orket.orket import ConfigLoader
from orket.schema import RockConfig, EpicConfig, IssueConfig

class StructuralReconciler:
    """
    Ensures structural integrity of the project board.
    Finds orphans and adopts them into 'Run the Business' or 'unplanned support'.
    """
    def __init__(self, root_path: Path = Path("model")):
        self.root_path = root_path
        self.default_rock_id = "run_the_business"
        self.default_epic_id = "unplanned_support"

    def reconcile_all(self):
        """Runs the full reconciliation sweep across all departments."""
        print("[RECONCILER] Starting organizational structural audit...")
        
        # 1. Gather all linked assets to identify orphans
        linked_epics = set()
        linked_issues = set()
        
        # Scan Rocks for linked Epics
        for dept_dir in self.root_path.iterdir():
            if not dept_dir.is_dir(): continue
            rock_path = dept_dir / "rocks"
            if rock_path.exists():
                for rf in rock_path.glob("*.json"):
                    try:
                        data = json.loads(rf.read_text(encoding="utf-8"))
                        for e in data.get("epics", []):
                            linked_epics.add(e["epic"])
                    except (json.JSONDecodeError, OSError, KeyError) as e:
                        print(f"  [RECONCILER] WARN: Failed to parse rock {rf.name}: {e}")
                        continue

        # Scan Epics for linked Issues
        for dept_dir in self.root_path.iterdir():
            if not dept_dir.is_dir(): continue
            epic_path = dept_dir / "epics"
            if epic_path.exists():
                for ef in epic_path.glob("*.json"):
                    try:
                        data = json.loads(ef.read_text(encoding="utf-8"))
                        for i in data.get("issues", []) or data.get("stories", []):
                            # Issues are usually embedded, but we track names to find standalone orphan files
                            linked_issues.add(i.get("id") or i.get("name") or i.get("summary"))
                    except (json.JSONDecodeError, OSError, KeyError) as e:
                        print(f"  [RECONCILER] WARN: Failed to parse rock {rf.name}: {e}")
                        continue

        # 2. Adopt Orphaned Epics into 'Run the Business'
        self._adopt_epics(linked_epics)
        
        # 3. Adopt Orphaned Issues into 'unplanned support'
        self._adopt_issues(linked_issues)

    def _adopt_epics(self, linked_epics: set):
        rtb_path = self.root_path / "core" / "rocks" / f"{self.default_rock_id}.json"
        if not rtb_path.exists(): return
        
        rtb_data = json.loads(rtb_path.read_text(encoding="utf-8"))
        dirty = False

        for dept_dir in self.root_path.iterdir():
            if not dept_dir.is_dir(): continue
            epic_path = dept_dir / "epics"
            if epic_path.exists():
                for ef in epic_path.glob("*.json"):
                    epic_id = ef.stem
                    if epic_id == self.default_epic_id: continue # Don't adopt the catchment area
                    
                    if epic_id not in linked_epics:
                        print(f"  [RECONCILER] Adopting orphan Epic: {epic_id} into 'Run the Business'")
                        rtb_data["epics"].append({
                            "epic": epic_id,
                            "department": dept_dir.name
                        })
                        linked_epics.add(epic_id)
                        dirty = True
        
        if dirty:
            rtb_path.write_text(json.dumps(rtb_data, indent=4), encoding="utf-8")

    def _adopt_issues(self, linked_issues: set):
        ups_path = self.root_path / "core" / "epics" / f"{self.default_epic_id}.json"
        if not ups_path.exists(): return
        
        ups_data = json.loads(ups_path.read_text(encoding="utf-8"))
        dirty = False

        for dept_dir in self.root_path.iterdir():
            if not dept_dir.is_dir(): continue
            issue_dir = dept_dir / "issues"
            if issue_dir.exists():
                for isf in issue_dir.glob("*.json"):
                    issue_id = isf.stem
                    if issue_id not in linked_issues:
                        print(f"  [RECONCILER] Adopting orphan standalone Issue: {issue_id} into 'unplanned support'")
                        # Load issue data to embed it
                        try:
                            issue_data = json.loads(isf.read_text(encoding="utf-8"))
                            if "issues" not in ups_data: ups_data["issues"] = []
                            ups_data["issues"].append(issue_data)
                            dirty = True
                        except (json.JSONDecodeError, OSError, KeyError) as e:
                            print(f"  [RECONCILER] WARN: Failed to parse issue {isf.name}: {e}")
                            continue
        
        if dirty:
            ups_path.write_text(json.dumps(ups_data, indent=4), encoding="utf-8")
