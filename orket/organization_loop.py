import asyncio
from pathlib import Path
from typing import Optional, List

from orket.infrastructure.async_file_tools import AsyncFileTools
from orket.orket import ConfigLoader, ExecutionPipeline
from orket.schema import CardStatus, RockConfig, EpicConfig, OrganizationConfig
from orket.domain.critical_path import CriticalPathEngine

class OrganizationLoop:
    def __init__(self, organization_path: Path = Path("config/organization.json")):
        self.org_path = organization_path
        self.fs = AsyncFileTools(Path("."))
        if not self.org_path.exists():
            self.org_path = Path("model/organization.json")
        self.org = self._load_org()
        self.running = False

    def _load_org(self) -> OrganizationConfig:
        return OrganizationConfig.model_validate_json(self.fs.read_file_sync(str(self.org_path)))

    async def run_forever(self):
        self.running = True
        print(f"--- [Vibe Rail Organization Loop Started] ---")
        while self.running:
            # 1. Scan for next priority work based on Critical Path
            next_card = self._find_next_critical_card()
            
            if next_card:
                print(f"--- [EXECUTING CRITICAL PATH CARD: {next_card['id']}] ---")
                pipeline = ExecutionPipeline(Path("workspace/default"), next_card['dept'])
                await pipeline.run_card(next_card['id'])
            else:
                # Idle jitter
                await asyncio.sleep(10)

    def _find_next_critical_card(self) -> Optional[dict]:
        """Finds the most critical READY card across all departments."""
        candidates = []
        
        for dept in self.org.departments:
            loader = ConfigLoader(Path("model"), dept)
            for epic_name in loader.list_assets("epics"):
                try:
                    epic = loader.load_asset("epics", epic_name, EpicConfig)
                    # Use Engine to get sorted IDs
                    priority_ids = CriticalPathEngine.get_priority_queue(epic)
                    
                    if priority_ids:
                        top_id = priority_ids[0]
                        # Fetch original issue for priority check
                        issue = next(i for i in epic.issues if i.id == top_id)
                        candidates.append({
                            "id": top_id,
                            "weight": len(priority_ids), # Simplified global weight
                            "priority": issue.priority,
                            "dept": dept
                        })
                except (FileNotFoundError, ValueError, StopIteration) as e:
                    # Log skip for visibility but continue scan
                    print(f"  [ORG_LOOP] WARN: Skipping epic {epic_name} in {dept}: {e}")
                    continue
        
        if not candidates: return None
            
        # Sort by Weight (Length of remaining critical path) then Priority
        p_map = {"High": 0, "Medium": 1, "Low": 2}
        candidates.sort(key=lambda x: (-x["weight"], p_map.get(x["priority"], 3)))
        
        return candidates[0]
