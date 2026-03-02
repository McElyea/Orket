import httpx
from typing import List, Optional
from orket.vendors.base import VendorInterface, VendorRock, VendorEpic, VendorCard

class GiteaVendor(VendorInterface):
    """
    Gitea Integration.
    Rock = Milestone
    Epic = Label/Project
    Card = Issue
    """
    def __init__(self, base_url: str, token: str, owner: str, repo: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"token {token}", "Accept": "application/json"}
        self.repo_api = f"{self.base_url}/api/v1/repos/{owner}/{repo}"

    @staticmethod
    def _coerce_label_id(epic_id: Optional[str]) -> Optional[int]:
        token = str(epic_id or "").strip()
        if not token:
            return None
        try:
            parsed = int(token)
        except (TypeError, ValueError) as exc:
            raise ValueError("epic_id must be an integer label id") from exc
        if parsed <= 0:
            raise ValueError("epic_id must be a positive integer label id")
        return parsed

    async def get_rocks(self) -> List[VendorRock]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.repo_api}/milestones", headers=self.headers)
            resp.raise_for_status()
            data = resp.json()
            return [VendorRock(id=str(m["id"]), name=m["title"], description=m["description"], status=m["state"]) for m in data]

    async def get_epics(self, rock_id: Optional[str] = None) -> List[VendorEpic]:
        # In Gitea, we might use Labels as Epics
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.repo_api}/labels", headers=self.headers)
            resp.raise_for_status()
            return [VendorEpic(id=str(l["id"]), name=l["name"], description=l["description"]) for l in resp.json()]

    async def get_cards(self, epic_id: Optional[str] = None) -> List[VendorCard]:
        # In Gitea, we filter Issues by milestone (Rock) or label (Epic)
        params = {}
        label_id = self._coerce_label_id(epic_id)
        if label_id is not None:
            params["labels"] = str(label_id)
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.repo_api}/issues", headers=self.headers, params=params)
            resp.raise_for_status()
            return [VendorCard(
                id=str(i["number"]), 
                summary=i["title"], 
                description=i["body"], 
                status="ready" if i["state"] == "open" else "done",
                priority="Medium" 
            ) for i in resp.json()]

    async def update_card_status(self, card_id: str, status: str) -> bool:
        state = "closed" if status == "done" else "open"
        async with httpx.AsyncClient() as client:
            resp = await client.patch(f"{self.repo_api}/issues/{card_id}", headers=self.headers, json={"state": state})
            return resp.is_success

    async def add_card(self, epic_id: str, summary: str, description: str) -> VendorCard:
        label_id = self._coerce_label_id(epic_id)
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.repo_api}/issues", headers=self.headers, json={
                "title": summary,
                "body": description,
                "labels": [label_id] if label_id is not None else []
            })
            i = resp.json()
            return VendorCard(id=str(i["number"]), summary=i["title"], status="ready", priority="Medium")

    async def get_card_details(self, card_id: str) -> VendorCard:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.repo_api}/issues/{card_id}", headers=self.headers)
            i = resp.json()
            return VendorCard(id=str(i["number"]), summary=i["title"], description=i["body"], status=i["state"], priority="Medium")
