import asyncio
from pathlib import Path
from typing import Optional

from orket.orket import ConfigLoader, ExecutionPipeline
from orket.schema import CardStatus, RockConfig, EpicConfig, OrganizationConfig

class OrganizationLoop:
    def __init__(self, organization_path: Path = Path("model/organization.json")):
        self.org_path = organization_path
        self.org = self._load_org()
        self.running = False

    def _load_org(self) -> OrganizationConfig:
        return OrganizationConfig.model_validate_json(self.org_path.read_text(encoding="utf-8"))

    async def run_forever(self):
        self.running = True
        print(f"--- [McElyea Organization Loop Started] ---")
        while self.running:
            # 1. Scan for next priority work
            next_card = self._find_next_ready_card()
            
            if next_card:
                print(f"--- [EXECUTING PRIORITY CARD: {next_card['id']}] ---")
                pipeline = ExecutionPipeline(Path("workspace/default"), next_card['dept'])
                # Execute the card
                await pipeline.run_card(next_card['id'])
            else:
                # Idle jitter
                await asyncio.sleep(10)

    def _find_next_ready_card(self) -> Optional[dict]:
        found_cards = []
        for dept in self.org.departments:
            loader = ConfigLoader(Path("model"), dept)
            for epic_name in loader.list_assets("epics"):
                epic = loader.load_asset("epics", epic_name, EpicConfig)
                for issue in epic.issues:
                    if issue.status == CardStatus.READY:
                        found_cards.append({
                            "id": issue.id,
                            "priority": issue.priority,
                            "dept": dept
                        })
        
        if not found_cards:
            return None
            
        # Priority mapping
        p_map = {"High": 0, "Medium": 1, "Low": 2}
        found_cards.sort(key=lambda x: p_map.get(x["priority"], 3))
        
        return found_cards[0]