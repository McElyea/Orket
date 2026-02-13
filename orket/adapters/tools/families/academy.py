from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List

from orket.adapters.tools.families.base import BaseTools
from orket.time_utils import now_local


class AcademyTools(BaseTools):
    def __init__(self, workspace_root: Path, references: List[Path]):
        super().__init__(workspace_root, references)
        from orket.adapters.storage.async_file_tools import AsyncFileTools

        self.project_root = self.workspace_root.parent.parent
        self.async_fs = AsyncFileTools(self.project_root)

    def archive_eval(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        session_id = args.get("session_id")
        if not session_id:
            return {"ok": False, "error": "session_id required"}

        src = self.workspace_root.parent / "runs" / session_id
        dest = self.workspace_root.parent.parent / "evals" / f"{now_local().strftime('%Y%m%d_%H%M%S')}_{args.get('label', 'trial')}"

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dest)
            return {"ok": True, "path": str(dest)}
        except (OSError, shutil.Error, RuntimeError, ValueError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}

    async def promote_prompt(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        seat, content = args.get("seat"), args.get("content")
        if not seat or not content:
            return {"ok": False, "error": "Missing params"}
        from orket.utils import sanitize_name

        relative_dest = Path("prompts") / sanitize_name(seat) / f"{args.get('model_family', 'qwen')}.txt"
        try:
            path = await self.async_fs.write_file(str(relative_dest), content)
            return {"ok": True, "path": path}
        except (PermissionError, OSError, ValueError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}

