from pathlib import Path
from typing import List, Dict, Any
from orket.orket import ConfigLoader
from orket.schema import RockConfig, EpicConfig, IssueConfig

def get_board_hierarchy(department: str = "core", auto_fix: bool = False) -> Dict[str, Any]:
    """
    Builds a tree: Rock -> Epic -> Issue
    Identifies orphaned Epics (no Rock) and orphaned Issues (no Epic).
    """
    loader = ConfigLoader(Path("model"), department)
    
    rocks_names = loader.list_assets("rocks")
    epics_names = loader.list_assets("epics")
    issues_names = loader.list_assets("issues")
    
    hierarchy = {
        "rocks": [],
        "orphaned_epics": [],
        "orphaned_issues": [],
        "artifacts": [f.name for f in (Path("model") / department / "artifacts").iterdir() if f.is_file()] if (Path("model") / department / "artifacts").exists() else [],
        "alerts": []
    }
    
    epics_in_rocks = set()
    issues_in_epics = set()
    
    # 1. Process Rocks
    for rname in rocks_names:
        try:
            rock = loader.load_asset("rocks", rname, RockConfig)
            rock_node = {
                "id": rname,
                "name": rock.name,
                "description": rock.description,
                "status": rock.status,
                "epics": []
            }
            
            for entry in rock.epics:
                ename = entry["epic"]
                edept = entry["department"]
                epics_in_rocks.add(ename)
                
                try:
                    dept_loader = ConfigLoader(Path("model"), edept)
                    epic = dept_loader.load_asset("epics", ename, EpicConfig)
                    
                    # Track issues in this epic
                    epic_issues = []
                    for i in epic.issues:
                        # We use summary as a weak ID for now to see if it's a 'named' standalone issue
                        issues_in_epics.add(i.name) 
                        issue_dict = i.model_dump(by_alias=True)
                        issue_dict["name"] = i.name # Ensure name is present for UI
                        epic_issues.append(issue_dict)

                    epic_node = {
                        "id": ename,
                        "name": epic.name,
                        "description": epic.description,
                        "status": epic.status,
                        "issues": epic_issues
                    }
                    rock_node["epics"].append(epic_node)
                except Exception as e:
                    rock_node["epics"].append({"id": ename, "name": ename, "error": str(e)})
            
            hierarchy["rocks"].append(rock_node)
        except Exception:
            pass

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
                    "issues": []
                }
                for i in epic.issues:
                    issues_in_epics.add(i.name)
                    issue_dict = i.model_dump(by_alias=True)
                    issue_dict["name"] = i.name
                    orph_epic["issues"].append(issue_dict)
                hierarchy["orphaned_epics"].append(orph_epic)
            except Exception:
                pass

    # 3. Find Orphaned Issues (Standalone files not referenced in any Epic)
    for iname in issues_names:
        try:
            issue = loader.load_asset("issues", iname, IssueConfig)
            if issue.name not in issues_in_epics:
                issue_dict = issue.model_dump(by_alias=True)
                issue_dict["name"] = issue.name
                hierarchy["orphaned_issues"].append(issue_dict)
        except Exception:
            pass

    if hierarchy["orphaned_epics"] or hierarchy["orphaned_issues"]:
        msg = f"Structure Alert: {len(hierarchy['orphaned_epics'])} Orphan Epics, {len(hierarchy['orphaned_issues'])} Orphaned Issues."
        hierarchy["alerts"].append({
            "type": "error",
            "message": msg,
            "action_required": "Assign orphans to parent structures to maintain engine integrity."
        })
                
    return hierarchy
