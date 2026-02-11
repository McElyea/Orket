import json
import os
import shutil
from datetime import datetime, UTC
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional

from orket.infrastructure.sqlite_repositories import SQLiteCardRepository
from orket.settings import get_setting

class BaseTools:
    def __init__(self, workspace_root: Path, references: List[Path]):
        self.workspace_root = workspace_root
        self.references = references

    def _resolve_safe_path(self, path_str: str, write: bool = False) -> Path:
        """
        Resolve and validate a file path against security policy.
        """
        from orket.domain.verification import AGENT_OUTPUT_DIR, VERIFICATION_DIR
        
        p = Path(path_str)
        if not p.is_absolute():
            p = self.workspace_root / p

        resolved = p.resolve()
        workspace_resolved = self.workspace_root.resolve()

        # Check if within workspace
        in_workspace = resolved.is_relative_to(workspace_resolved)
        in_references = any(resolved.is_relative_to(r.resolve()) for r in self.references)

        if not (in_workspace or in_references):
            raise PermissionError(f"Access to path '{path_str}' is denied by security policy.")

        if write:
            # We enforce workspace boundaries. 
            # Architectural governance is handled by ToolGate.
            if not in_workspace:
                raise PermissionError(f"Write access to path '{path_str}' is denied.")

        return resolved

class FileSystemTools(BaseTools):
    def __init__(self, workspace_root: Path, references: List[Path]):
        super().__init__(workspace_root, references)
        from orket.infrastructure.async_file_tools import AsyncFileTools
        self.async_fs = AsyncFileTools(workspace_root, references)

    async def read_file(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            path_str = args.get("path")
            content = await self.async_fs.read_file(path_str)
            return {"ok": True, "content": content}
        except FileNotFoundError: return {"ok": False, "error": "File not found"}
        except Exception as e: return {"ok": False, "error": str(e)}

    async def write_file(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            path_str = args.get("path")
            content = args.get("content")
            path = await self.async_fs.write_file(path_str, content)
            return {"ok": True, "path": path}
        except Exception as e: return {"ok": False, "error": str(e)}

    async def list_directory(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            path_str = args.get("path", ".")
            items = await self.async_fs.list_directory(path_str)
            return {"ok": True, "items": items}
        except FileNotFoundError: return {"ok": False, "error": "Dir not found"}
        except Exception as e: return {"ok": False, "error": str(e)}

class VisionTools(BaseTools):
    def __init__(self, workspace_root: Path, references: List[Path]):
        super().__init__(workspace_root, references)
        self._image_pipeline = None

    def image_analyze(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        return {"ok": False, "error": "Visual analysis tool not implemented. Image analysis requires a vision-capable model or secondary API."}

    def image_generate(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            path = self._resolve_safe_path(args.get("path", "generated.png"), write=True)
            if self._image_pipeline is None:
                try:
                    import torch
                    from diffusers import StableDiffusionPipeline
                except ImportError:
                    return {"ok": False, "error": "Dependencies missing: pip install torch diffusers transformers accelerate"}

                model_id = get_setting("sd_model", "runwayml/stable-diffusion-v1-5")
                device = "cuda" if torch.cuda.is_available() else "cpu"
                dtype = torch.float16 if device == "cuda" else torch.float32
                
                print(f"  [SYSTEM] Loading Stable Diffusion ({model_id}) on {device}...")
                self._image_pipeline = StableDiffusionPipeline.from_pretrained(model_id, torch_dtype=dtype)
                self._image_pipeline.to(device)

            image = self._image_pipeline(args.get("prompt")).images[0]
            path.parent.mkdir(parents=True, exist_ok=True)
            image.save(path)
            return {"ok": True, "path": str(path)}
        except Exception as e: return {"ok": False, "error": str(e)}

class CardManagementTools(BaseTools):
    def __init__(self, workspace_root: Path, references: List[Path], db_path: str = "orket_persistence.db", cards_repo: Optional[AsyncCardRepository] = None):
        super().__init__(workspace_root, references)
        from orket.infrastructure.async_card_repository import AsyncCardRepository
        self.cards = cards_repo or AsyncCardRepository(db_path)

    async def create_issue(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        session_id, seat, summary = context.get("session_id"), args.get("seat"), args.get("summary")
        if not all([session_id, seat, summary]): return {"ok": False, "error": "Missing params"}
        # Note: add_issue is currently in SQLiteCardRepository but not in AsyncCardRepository interface.
        # I'll use save() which is polymorphic.
        import uuid
        issue_id = f"ISSUE-{str(uuid.uuid4())[:4].upper()}"
        card_data = {
            "id": issue_id,
            "session_id": session_id,
            "seat": seat,
            "summary": summary,
            "type": args.get("type", "story"),
            "priority": args.get("priority", "Medium"),
            "status": "ready"
        }
        await self.cards.save(card_data)
        return {"ok": True, "issue_id": issue_id}

    async def update_issue_status(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        from orket.schema import CardStatus
        issue_id = args.get("issue_id") or context.get("issue_id")
        new_status_str, role = args.get("status", "").lower(), context.get("role", "")
        if not issue_id or not new_status_str: return {"ok": False, "error": "Missing params"}
        
        try:
            new_status = CardStatus(new_status_str)
        except ValueError:
            return {"ok": False, "error": f"Invalid status: {new_status_str}"}

        if new_status == CardStatus.CANCELED and "project_manager" not in role.lower():
            return {"ok": False, "error": "Permission Denied: Only PM can cancel work."}
            
        await self.cards.update_status(issue_id, new_status)
        return {"ok": True, "issue_id": issue_id, "status": new_status.value}

    async def add_issue_comment(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        issue_id, content = context.get("issue_id"), args.get("comment")
        if not issue_id or not content: return {"ok": False, "error": "Missing params"}
        await self.cards.add_comment(issue_id, context.get("role", "Unknown"), content)
        return {"ok": True, "message": "Comment added."}

    async def get_issue_context(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        issue_id = args.get("issue_id") or context.get("issue_id")
        if not issue_id: return {"ok": False, "error": "No issue_id"}
        comments = await self.cards.get_comments(issue_id)
        issue_data = await self.cards.get_by_id(issue_id) or {}
        return {"ok": True, "status": issue_data.get("status"), "summary": issue_data.get("summary"), "comments": comments}

class AcademyTools(BaseTools):
    def archive_eval(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        session_id = args.get("session_id")
        if not session_id: return {"ok": False, "error": "session_id required"}
        
        # Resolve source from workspace relative path
        src = self.workspace_root.parent / "runs" / session_id
        # Resolve destination from project root (or as per system policy)
        dest = self.workspace_root.parent.parent / "evals" / f"{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{args.get('label', 'trial')}"
        
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dest)
            return {"ok": True, "path": str(dest)}
        except Exception as e: return {"ok": False, "error": str(e)}

    def promote_prompt(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        seat, content = args.get("seat"), args.get("content")
        if not seat or not content: return {"ok": False, "error": "Missing params"}
        from orket.utils import sanitize_name
        # Resolve destination from project root
        dest = self.workspace_root.parent.parent / "prompts" / sanitize_name(seat) / f"{args.get('model_family', 'qwen')}.txt"
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            return {"ok": True, "path": str(dest)}
        except Exception as e: return {"ok": False, "error": str(e)}

class ToolBox:
    def __init__(self, policy, workspace_root: str, references: List[str], db_path: str = "orket_persistence.db", cards_repo: Optional[AsyncCardRepository] = None):
        self.root = Path(workspace_root)
        self.refs = [Path(r) for r in references]
        self.db_path = db_path
        self.fs = FileSystemTools(self.root, self.refs)
        self.vision = VisionTools(self.root, self.refs)
        self.cards = CardManagementTools(self.root, self.refs, db_path=self.db_path, cards_repo=cards_repo)
        self.academy = AcademyTools(self.root, self.refs)

    async def execute(self, tool_name: str, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a tool by name with provided arguments and context.
        """
        tool_map = get_tool_map(self)
        if tool_name not in tool_map:
            return {"ok": False, "error": f"Unknown tool '{tool_name}'"}
        
        tool_fn = tool_map[tool_name]
        try:
            import inspect
            if inspect.iscoroutinefunction(tool_fn):
                return await tool_fn(args, context=context)
            else:
                return tool_fn(args, context=context)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def nominate_card(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        from orket.logging import log_event
        log_event("card_nomination", {**args, "nominated_by": context.get("role")}, self.root, role="SYS")
        return {"ok": True, "message": "Nomination recorded."}

    def report_credits(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        issue_id, amount = context.get("issue_id"), args.get("amount", 0.0)
        if not issue_id or amount <= 0: return {"ok": False, "error": "Invalid params"}
        self.cards.cards.add_credits(issue_id, amount)
        return {"ok": True, "message": f"Reported {amount} credits."}

    def refinement_proposal(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        from orket.logging import log_event
        log_event("refinement_proposed", args, self.root, role="SYS")
        return {"ok": True, "message": "Proposal logged."}

    def request_excuse(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        issue_id = context.get("issue_id")
        if not issue_id: return {"ok": False, "error": "No active Issue"}
        self.cards.cards.update_issue_status(issue_id, "excuse_requested")
        return {"ok": True, "message": "Excuse requested."}

def get_tool_map(toolbox: ToolBox) -> Dict[str, Callable]:
    return {
        "read_file": toolbox.fs.read_file,
        "write_file": toolbox.fs.write_file,
        "list_directory": toolbox.fs.list_directory,
        "image_analyze": toolbox.vision.image_analyze,
        "image_generate": toolbox.vision.image_generate,
        "create_issue": toolbox.cards.create_issue,
        "update_issue_status": toolbox.cards.update_issue_status,
        "add_issue_comment": toolbox.cards.add_issue_comment,
        "get_issue_context": toolbox.cards.get_issue_context,
        "nominate_card": toolbox.nominate_card,
        "report_credits": toolbox.report_credits,
        "refinement_proposal": toolbox.refinement_proposal,
        "request_excuse": toolbox.request_excuse,
        "archive_eval": toolbox.academy.archive_eval,
        "promote_prompt": toolbox.academy.promote_prompt,
    }