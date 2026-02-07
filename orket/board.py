from pathlib import Path
from typing import List, Dict, Any
from orket.orket import ConfigLoader
from orket.schema import RockConfig, EpicConfig, BookConfig

def get_board_hierarchy(department: str = "core", auto_fix: bool = False) -> Dict[str, Any]:
    """
    Builds a tree: Rock -> Epic -> Book
    Identifies orphaned Epics (no Rock).
    """
    loader = ConfigLoader(Path("model"), department)
    
    rocks_names = loader.list_assets("rocks")
    epics_names = loader.list_assets("epics")
    
    hierarchy = {
        "rocks": [],
        "orphaned_epics": [],
        "alerts": []
    }
    
    epics_in_rocks = set()
    
    # 1. Process Rocks
    for rname in rocks_names:
        try:
            rock = loader.load_asset("rocks", rname, RockConfig)
            rock_node = {
                "name": rock.name,
                "description": rock.description,
                "epics": []
            }
            
            for entry in rock.epics:
                ename = entry["epic"]
                edept = entry["department"]
                epics_in_rocks.add(ename)
                
                try:
                    dept_loader = ConfigLoader(Path("model"), edept)
                    epic = dept_loader.load_asset("epics", ename, EpicConfig)
                    epic_node = {
                        "name": epic.name,
                        "description": epic.description,
                        "books": [b.dict() for b in epic.books]
                    }
                    rock_node["epics"].append(epic_node)
                except Exception as e:
                    rock_node["epics"].append({"name": ename, "error": str(e)})
            
            hierarchy["rocks"].append(rock_node)
        except Exception:
            pass

    # 2. Find Orphaned Epics (Standalone Epics)
    orphans = []
    for ename in epics_names:
        if ename not in epics_in_rocks:
            try:
                epic = loader.load_asset("epics", ename, EpicConfig)
                orphans.append({
                    "name": epic.name,
                    "description": epic.description,
                    "books": [b.dict() for b in epic.books]
                })
            except Exception:
                pass
    
    hierarchy["orphaned_epics"] = orphans

    if orphans:
        hierarchy["alerts"].append({
            "type": "error",
            "message": f"Found {len(orphans)} orphaned Epics. All work should belong to a Rock.",
            "action_required": "Assign these to a Rock (e.g., maintenance) or they will be auto-grouped."
        })
        
        if auto_fix:
            # Logic to create a 'maintenance' rock if it doesn't exist and add orphans
            pass
                
    return hierarchy
