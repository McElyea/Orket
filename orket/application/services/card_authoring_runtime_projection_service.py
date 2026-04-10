from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.core.domain.records import IssueRecord
from orket.schema import CardStatus, CardType

AUTHORED_CARDS_EPIC_ID = "orket_ui_authored_cards"
AUTHORED_CARDS_EPIC_RELATIVE_PATH = f"config/epics/{AUTHORED_CARDS_EPIC_ID}.json"


class CardAuthoringRuntimeProjectionService:
    """Projects authored issue cards onto a loader-backed epic for runtime resolution."""

    def __init__(self, *, project_root: Path, file_tools: AsyncFileTools | None = None) -> None:
        self._project_root = Path(project_root).resolve()
        self._file_tools = file_tools or AsyncFileTools(self._project_root)

    async def upsert_card_record(self, record: IssueRecord) -> None:
        if record.type != CardType.ISSUE:
            return

        payload = await self._load_epic_payload()
        payload.update(
            {
                "id": AUTHORED_CARDS_EPIC_ID,
                "name": AUTHORED_CARDS_EPIC_ID,
                "description": "Synthetic runtime projection for OrketUI-authored issue cards.",
                "team": "standard",
                "environment": "standard",
                "architecture_governance": {"idesign": False, "pattern": "Standard"},
            }
        )

        issues = payload.get("issues")
        issue_rows = list(issues) if isinstance(issues, list) else []
        projected_issue = self._build_issue_payload(record)

        for index, existing in enumerate(issue_rows):
            if str((existing or {}).get("id") or "").strip() == record.id:
                issue_rows[index] = projected_issue
                break
        else:
            issue_rows.append(projected_issue)

        payload["issues"] = issue_rows
        serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        await self._file_tools.write_file(AUTHORED_CARDS_EPIC_RELATIVE_PATH, serialized)

    async def _load_epic_payload(self) -> dict[str, Any]:
        try:
            raw = await self._file_tools.read_file(AUTHORED_CARDS_EPIC_RELATIVE_PATH)
        except FileNotFoundError:
            return {"issues": []}

        loaded = json.loads(raw)
        if not isinstance(loaded, dict):
            raise ValueError("card_authoring_runtime_projection_epic_invalid")
        return loaded

    def _build_issue_payload(self, record: IssueRecord) -> dict[str, Any]:
        params = dict(record.params or {})
        purpose = str(params.get("purpose") or "").strip()
        requirements = str(params.get("prompt") or "").strip()
        return {
            "id": record.id,
            "summary": record.summary,
            "seat": record.seat,
            "status": record.status.value if isinstance(record.status, CardStatus) else str(record.status),
            "priority": record.priority,
            "description": purpose or None,
            "requirements": requirements or None,
            "note": record.note,
            "params": params,
            "depends_on": list(record.depends_on or []),
            "verification": dict(record.verification or {}),
            "metrics": dict(record.metrics or {}),
        }
