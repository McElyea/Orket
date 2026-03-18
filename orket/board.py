import asyncio
from pathlib import Path
from typing import Any, Dict

from orket.orket import ConfigLoader
from orket.exceptions import CardNotFound
from orket.schema import EpicConfig, IssueConfig, RockConfig


def _append_load_failure(
    hierarchy: Dict[str, Any],
    *,
    asset_type: str,
    asset_name: str,
    department: str,
    stage: str,
    error: Exception,
) -> None:
    hierarchy["load_failures"].append(
        {
            "asset_type": asset_type,
            "asset_name": asset_name,
            "department": department,
            "stage": stage,
            "error": str(error),
        }
    )


def get_board_hierarchy(department: str = "core", auto_fix: bool = False) -> Dict[str, Any]:
    """
    CLI/test helper that builds a tree: Rock -> Epic -> Issue.
    Blocks the calling thread while loading config assets.
    """
    auto_fix_error: Exception | None = None
    if auto_fix:
        try:
            from orket.domain.reconciler import StructuralReconciler

            StructuralReconciler().reconcile_all()
        except (RuntimeError, ValueError, OSError, ImportError) as exc:
            auto_fix_error = exc

    loader = ConfigLoader(Path("model"), department)

    rocks_names = loader.list_assets("rocks")
    epics_names = loader.list_assets("epics")
    issues_names = loader.list_assets("issues")

    artifacts = []
    artifacts_dir = Path("model") / department / "artifacts"
    if artifacts_dir.exists():
        try:
            artifacts = [f.name for f in artifacts_dir.iterdir() if f.is_file()]
        except OSError:
            artifacts = []

    hierarchy = {
        "rocks": [],
        "orphaned_epics": [],
        "orphaned_issues": [],
        "artifacts": artifacts,
        "alerts": [],
        "load_failures": [],
        "result_status": "success",
    }
    if auto_fix:
        if auto_fix_error is None:
            hierarchy["alerts"].append(
                {
                    "type": "info",
                    "message": "auto_fix requested: startup reconciliation executed before hierarchy load.",
                    "action_required": "none",
                }
            )
        else:
            _append_load_failure(
                hierarchy,
                asset_type="board",
                asset_name="auto_fix",
                department=department,
                stage="auto_fix",
                error=auto_fix_error,
            )

    epics_in_rocks = set()
    issue_ids_in_epics = set()
    issue_names_in_epics = set()

    # 1. Process Rocks
    for rname in rocks_names:
        try:
            rock = loader.load_asset("rocks", rname, RockConfig)
            rock_node = {
                "id": rname,
                "name": rock.name,
                "description": rock.description,
                "status": rock.status,
                "epics": [],
            }

            for entry in rock.epics:
                ename = entry["epic"]
                edept = entry["department"]
                epics_in_rocks.add(ename)

                try:
                    dept_loader = ConfigLoader(Path("model"), edept)
                    epic = dept_loader.load_asset("epics", ename, EpicConfig)

                    # Track issue identity with stable IDs first, plus names for compatibility.
                    epic_issues = []
                    for i in epic.issues:
                        if getattr(i, "id", None):
                            issue_ids_in_epics.add(i.id)
                        if getattr(i, "name", None):
                            issue_names_in_epics.add(i.name)
                        issue_dict = i.model_dump(by_alias=True)
                        issue_dict["name"] = i.name
                        epic_issues.append(issue_dict)

                    epic_node = {
                        "id": ename,
                        "name": epic.name,
                        "description": epic.description,
                        "status": epic.status,
                        "issues": epic_issues,
                    }
                    rock_node["epics"].append(epic_node)
                except (FileNotFoundError, ValueError, CardNotFound, KeyError) as e:
                    _append_load_failure(
                        hierarchy,
                        asset_type="epic",
                        asset_name=ename,
                        department=edept,
                        stage="rock_epic_link_load",
                        error=e,
                    )
                    rock_node["epics"].append({"id": ename, "name": ename, "error": str(e)})

            hierarchy["rocks"].append(rock_node)
        except (FileNotFoundError, ValueError, CardNotFound) as e:
            _append_load_failure(
                hierarchy,
                asset_type="rock",
                asset_name=rname,
                department=department,
                stage="rock_load",
                error=e,
            )

    # 2. Find Orphaned Epics
    for ename in epics_names:
        if ename not in epics_in_rocks:
            try:
                epic = loader.load_asset("epics", ename, EpicConfig)
                orph_epic = {
                    "id": ename,
                    "name": epic.name,
                    "description": epic.description,
                    "status": epic.status,
                    "issues": [],
                }
                for i in epic.issues:
                    if getattr(i, "id", None):
                        issue_ids_in_epics.add(i.id)
                    if getattr(i, "name", None):
                        issue_names_in_epics.add(i.name)
                    issue_dict = i.model_dump(by_alias=True)
                    issue_dict["name"] = i.name
                    orph_epic["issues"].append(issue_dict)
                hierarchy["orphaned_epics"].append(orph_epic)
            except (FileNotFoundError, ValueError, CardNotFound) as e:
                _append_load_failure(
                    hierarchy,
                    asset_type="epic",
                    asset_name=ename,
                    department=department,
                    stage="orphan_epic_load",
                    error=e,
                )

    # 3. Find Orphaned Issues (Standalone files not referenced in any Epic)
    for iname in issues_names:
        try:
            issue = loader.load_asset("issues", iname, IssueConfig)
            issue_id = str(getattr(issue, "id", "") or "")
            issue_name = str(getattr(issue, "name", "") or "")
            is_referenced = issue_id in issue_ids_in_epics or (issue_name and issue_name in issue_names_in_epics)
            if not is_referenced:
                issue_dict = issue.model_dump(by_alias=True)
                issue_dict["name"] = issue.name
                hierarchy["orphaned_issues"].append(issue_dict)
        except (FileNotFoundError, ValueError, CardNotFound) as e:
            _append_load_failure(
                hierarchy,
                asset_type="issue",
                asset_name=iname,
                department=department,
                stage="issue_load",
                error=e,
            )

    if hierarchy["orphaned_epics"] or hierarchy["orphaned_issues"]:
        msg = (
            f"Structure Alert: {len(hierarchy['orphaned_epics'])} Orphan Epics, "
            f"{len(hierarchy['orphaned_issues'])} Orphaned Issues."
        )
        hierarchy["alerts"].append(
            {
                "type": "error",
                "message": msg,
                "action_required": "Assign orphans to parent structures to maintain engine integrity.",
            }
        )

    if hierarchy["load_failures"]:
        hierarchy["result_status"] = "partial_success"
        hierarchy["alerts"].append(
            {
                "type": "warning",
                "message": f"Partial board load: {len(hierarchy['load_failures'])} load failure(s).",
                "action_required": (
                    "Inspect load_failures for broken or missing assets before treating this hierarchy as complete."
                ),
            }
        )

    return hierarchy


async def get_board_hierarchy_async(
    department: str = "core",
    auto_fix: bool = False,
) -> Dict[str, Any]:
    return await asyncio.to_thread(get_board_hierarchy, department, auto_fix)
