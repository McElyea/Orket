from pathlib import Path
from typing import List, Dict, Any
from orket.orket import ConfigLoader
from orket.schema import RockConfig, EpicConfig, CardConfig

def get_board_hierarchy(department: str = "core", auto_fix: bool = False) -> Dict[str, Any]:
    """
    Builds a tree: Rock -> Epic -> Card
    Identifies orphaned Epics (no Rock) and orphaned Cards (no Epic).
    """
    loader = ConfigLoader(Path("model"), department)
    
    rocks_names = loader.list_assets("rocks")
    epics_names = loader.list_assets("epics")
    cards_names = loader.list_assets("cards")
    
    hierarchy = {
        "rocks": [],
        "orphaned_epics": [],
        "orphaned_cards": [],
        "alerts": []
    }
    
    epics_in_rocks = set()
    cards_in_epics = set()
    
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
                    
                    # Track cards in this epic
                    epic_cards = []
                    for c in epic.cards:
                        cards_in_epics.add(c.summary) 
                        epic_cards.append(c.dict())

                    epic_node = {
                        "name": epic.name,
                        "description": epic.description,
                        "cards": epic_cards
                    }
                    rock_node["epics"].append(epic_node)
                except Exception as e:
                    rock_node["epics"].append({"name": ename, "error": str(e)})
            
            hierarchy["rocks"].append(rock_node)
        except Exception:
            pass

    # 2. Find Orphaned Epics
    for ename in epics_names:
        if ename not in epics_in_rocks:
            try:
                epic = loader.load_asset("epics", ename, EpicConfig)
                orph_epic = {
                    "name": epic.name,
                    "description": epic.description,
                    "cards": []
                }
                for c in epic.cards:
                    cards_in_epics.add(c.summary)
                    orph_epic["cards"].append(c.dict())
                hierarchy["orphaned_epics"].append(orph_epic)
            except Exception:
                pass

    # 3. Find Orphaned Cards (Standalone files not referenced in any Epic)
    for cname in cards_names:
        try:
            card = loader.load_asset("cards", cname, CardConfig)
            if card.summary not in cards_in_epics:
                hierarchy["orphaned_cards"].append(card.dict())
        except Exception:
            pass

    if hierarchy["orphaned_epics"] or hierarchy["orphaned_cards"]:
        msg = f"Structure Alert: {len(hierarchy['orphaned_epics'])} Orphan Epics, {len(hierarchy['orphaned_cards'])} Orphaned Cards."
        hierarchy["alerts"].append({
            "type": "error",
            "message": msg,
            "action_required": "Assign orphans to parent structures to maintain engine integrity."
        })
                
    return hierarchy