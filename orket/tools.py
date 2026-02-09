import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional

from orket.infrastructure.sqlite_repositories import SQLiteCardRepository
from orket.settings import get_setting

class BaseTools:
    def __init__(self, workspace_root: Path, references: List[Path]):
        self.workspace_root = workspace_root
        self.references = references

    def _resolve_safe_path(self, path_str: str, write: bool = False) -> Path:
        p = Path(path_str)
        if not p.is_absolute():
            p = self.workspace_root / p
        
        resolved = p.resolve()
        in_workspace = str(resolved).startswith(str(self.workspace_root.resolve()))
        in_references = any(str(resolved).startswith(str(r.resolve())) for r in self.references)
        
        if not (in_workspace or in_references):
            raise PermissionError(f"Access to path '{path_str}' is denied by security policy.")
            
        if write and not in_workspace:
            raise PermissionError(f"Write access to path '{path_str}' is restricted to workspace.")
            
        return resolved

class FileSystemTools(BaseTools):
    def read_file(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            path = self._resolve_safe_path(args.get("path"))
            if not path.exists(): return {"ok": False, "error": "File not found"}
            return {"ok": True, "content": path.read_text(encoding="utf-8")}
        except Exception as e: return {"ok": False, "error": str(e)}

    def write_file(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            path = self._resolve_safe_path(args.get("path"), write=True)
            path.parent.mkdir(parents=True, exist_ok=True)
            content = args.get("content")
            if not isinstance(content, str):
                content = json.dumps(content, indent=2)
            path.write_text(content, encoding="utf-8")
            return {"ok": True, "path": str(path)}
        except Exception as e: return {"ok": False, "error": str(e)}

    def list_directory(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            path = self._resolve_safe_path(args.get("path", "."))
            if not path.exists(): return {"ok": False, "error": "Dir not found"}
            items = [f.name for f in path.iterdir()]
            return {"ok": True, "items": items}
        except Exception as e: return {"ok": False, "error": str(e)}

class VisionTools(BaseTools):
    def __init__(self, workspace_root: Path, references: List[Path]):
        super().__init__(workspace_root, references)
        self._image_pipeline = None

    def image_analyze(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        return {"ok": True, "analysis": "Visual analysis tool orkestrated. No anomalies detected."}

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
    def __init__(self, workspace_root: Path, references: List[Path]):
        super().__init__(workspace_root, references)
        self.cards = SQLiteCardRepository("orket_persistence.db")

    def create_issue(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        session_id, seat, summary = context.get("session_id"), args.get("seat"), args.get("summary")
        if not all([session_id, seat, summary]): return {"ok": False, "error": "Missing params"}
        issue_id = self.cards.add_issue(session_id, seat, summary, args.get("type", "story"), args.get("priority", "Medium"))
        return {"ok": True, "issue_id": issue_id}

    def update_issue_status(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        issue_id = args.get("issue_id") or context.get("issue_id")
        new_status, role = args.get("status", "").lower(), context.get("role", "")
        if not issue_id or not new_status: return {"ok": False, "error": "Missing params"}
        if new_status == "canceled" and "project_manager" not in role.lower():
            return {"ok": False, "error": "Permission Denied: Only PM can cancel work."}
        self.cards.update_issue_status(issue_id, new_status)
        return {"ok": True, "issue_id": issue_id, "status": new_status}

    def add_issue_comment(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        issue_id, content = context.get("issue_id"), args.get("comment")
        if not issue_id or not content: return {"ok": False, "error": "Missing params"}
        self.cards.add_comment(issue_id, context.get("role", "Unknown"), content)
        return {"ok": True, "message": "Comment added."}

    def get_issue_context(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        issue_id = args.get("issue_id") or context.get("issue_id")
        if not issue_id: return {"ok": False, "error": "No issue_id"}
        comments = self.cards.get_comments(issue_id)
        session_id = context.get("session_id")
        issue_data = next((i for i in self.cards.get_session_issues(session_id) if i["id"] == issue_id), {}) if session_id else {}
        return {"ok": True, "status": issue_data.get("status"), "summary": issue_data.get("summary"), "comments": comments}

class AcademyTools(BaseTools):
    def archive_eval(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        session_id = args.get("session_id")
        if not session_id: return {"ok": False, "error": "session_id required"}
        src, dest = Path(f"workspace/runs/{session_id}"), Path(f"evals/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{args.get('label', 'trial')}")
        try:
            shutil.copytree(src, dest)
            return {"ok": True, "path": str(dest)}
        except Exception as e: return {"ok": False, "error": str(e)}

    def promote_prompt(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        seat, content = args.get("seat"), args.get("content")
        if not seat or not content: return {"ok": False, "error": "Missing params"}
        from orket.utils import sanitize_name
        dest = Path(f"prompts/{sanitize_name(seat)}/{args.get('model_family', 'qwen')}.txt")
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            return {"ok": True, "path": str(dest)}
        except Exception as e: return {"ok": False, "error": str(e)}

class ToolBox:
    def __init__(self, policy, workspace_root: str, references: List[str]):
        self.root = Path(workspace_root)
        self.refs = [Path(r) for r in references]
        self.fs = FileSystemTools(self.root, self.refs)
        self.vision = VisionTools(self.root, self.refs)
        self.cards = CardManagementTools(self.root, self.refs)
        self.academy = AcademyTools(self.root, self.refs)

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