# orket/tools.py
import json
import os
import base64
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable

import fitz  # PyMuPDF
import docx
import ollama
from orket.hardware import ToolTier

# ------------------------------------------------------------
# Tool Implementation Core
# ------------------------------------------------------------

class ToolBox:
    def __init__(self, policy, workspace: str, references: List[str] = None):
        self.policy = policy
        self.workspace = Path(workspace).resolve()
        self.references = [Path(r).resolve() for r in (references or [])]
        self._image_pipeline = None

    def _resolve_safe_path(self, path_str: str, write: bool = False) -> Path:
        p = Path(path_str)
        if not p.is_absolute():
            p = (self.workspace / p).resolve()
        else:
            p = p.resolve()

        if write:
            if not self.policy.can_write(str(p)):
                raise PermissionError(f"Security Violation: Write access denied to {p}")
        else:
            if not self.policy.can_read(str(p)):
                found_in_ref = False
                for ref in self.references:
                    if str(p).startswith(str(ref)):
                        found_in_ref = True
                        break
                if not found_in_ref:
                    raise PermissionError(f"Security Violation: Read access denied to {p}")
        return p

    # --- File Tools ---

    def read_file(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            path = self._resolve_safe_path(args.get("path", ""))
            if not path.exists(): return {"ok": False, "error": "Not found"}
            return {"ok": True, "content": path.read_text(encoding="utf-8")}
        except Exception as e: return {"ok": False, "error": str(e)}

    def write_file(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            path = self._resolve_safe_path(args.get("path", ""), write=True)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(args.get("content", ""), encoding="utf-8")
            return {"ok": True, "path": str(path)}
        except Exception as e: return {"ok": False, "error": str(e)}

    def list_dir(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            path = self._resolve_safe_path(args.get("path", "."))
            items = [p.name for p in path.iterdir()]
            return {"ok": True, "items": items}
        except Exception as e: return {"ok": False, "error": str(e)}

    def document_inspect(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            path = self._resolve_safe_path(args.get("path", ""))
            ext = path.suffix.lower()
            if ext == ".pdf":
                text = ""
                with fitz.open(path) as doc:
                    for page in doc: text += page.get_text()
                return {"ok": True, "content": text, "type": "pdf"}
            elif ext == ".docx":
                doc = docx.Document(path)
                text = "\n".join([p.text for p in doc.paragraphs])
                return {"ok": True, "content": text, "type": "docx"}
            return {"ok": False, "error": "Unsupported format"}
        except Exception as e: return {"ok": False, "error": str(e)}

    # --- AI Tools ---

    async def image_analyze(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            path = self._resolve_safe_path(args.get("path", ""))
            with open(path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode('utf-8')
            client = ollama.AsyncClient()
            model = args.get("model", "llama3.2-vision")
            response = await client.generate(model=model, prompt=args.get("prompt", "Describe this image."), images=[img_data])
            return {"ok": True, "analysis": response['response']}
        except Exception as e: return {"ok": False, "error": str(e)}

    def image_generate(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            path = self._resolve_safe_path(args.get("path", "generated.png"), write=True)
            if self._image_pipeline is None:
                import torch
                from diffusers import StableDiffusionPipeline
                print("  [SYSTEM] Loading Stable Diffusion 1.5...")
                self._image_pipeline = StableDiffusionPipeline.from_pretrained("runwayml/stable-diffusion-v1-5", torch_dtype=torch.float16).to("cuda")
            image = self._image_pipeline(args.get("prompt")).images[0]
            path.parent.mkdir(parents=True, exist_ok=True)
            image.save(path)
            return {"ok": True, "path": str(path)}
        except Exception as e: return {"ok": False, "error": str(e)}

    # --- Traction & EOS Tools ---

    def create_issue(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Dynamically adds a new Issue to the Board."""
        session_id = context.get("session_id")
        seat = args.get("seat")
        summary = args.get("summary")
        issue_type = args.get("type", "story")
        if not session_id or not seat or not summary: return {"ok": False, "error": "Missing params"}
        
        from orket.persistence import PersistenceManager
        db = PersistenceManager()
        issue_id = db.add_issue(session_id, seat, summary, issue_type, args.get("priority", "Medium"))
        return {"ok": True, "issue_id": issue_id}

    def update_issue_status(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Updates Issue status. Only Project Manager can cancel."""
        issue_id = args.get("issue_id") or context.get("issue_id")
        new_status = args.get("status", "").lower()
        seat_calling = context.get("role", "")
        
        if not issue_id or not new_status: return {"ok": False, "error": "Missing params"}
        if new_status == "canceled" and "project_manager" not in seat_calling.lower():
            return {"ok": False, "error": "Permission Denied: Only PM can cancel work."}
            
        from orket.persistence import PersistenceManager
        db = PersistenceManager()
        db.update_issue_status(issue_id, new_status)
        return {"ok": True, "issue_id": issue_id, "status": new_status}

    def request_excuse(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Allows a member to request an excuse from the current issue."""
        issue_id = context.get("issue_id")
        reason = args.get("reason", "No reason provided")
        if not issue_id: return {"ok": False, "error": "No active Issue"}
        
        from orket.persistence import PersistenceManager
        db = PersistenceManager()
        db.update_issue_status(issue_id, "excuse_requested")
        print(f"  [PROTOCOL] Seat {context.get('role')} requested excuse from {issue_id}. Reason: {reason}")
        return {"ok": True, "message": "Excuse requested from Conductor."}

    # --- Academy Tools ---

    def archive_eval(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        session_id = args.get("session_id")
        if not session_id: return {"ok": False, "error": "session_id required"}
        src = Path(f"workspace/runs/{session_id}")
        dest = Path(f"evals/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{args.get('label', 'trial')}")
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

    def generate_reforge_report(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyzes logs/transcripts to generate a Reforge Audit."""
        workspace = self.workspace
        log_path = workspace / "orket.log"
        if not log_path.exists(): return {"ok": False, "error": "Logs not found."}
        logs = log_path.read_text(encoding="utf-8").splitlines()
        calls = [json.loads(l) for l in logs if "tool_call" in l]
        errs = [json.loads(l) for l in logs if "error" in l]
        report = {"session": context.get("session_id"), "stability": max(0, 10 - len(errs)), "calls": len(calls)}
        (workspace / "reforge_report.json").write_text(json.dumps(report, indent=2))
        return {"ok": True, "report": report}

# ------------------------------------------------------------
# Metadata & Registry
# ------------------------------------------------------------

TOOL_TIERS = {
    "read_file": ToolTier.TIER_0_UTILITY,
    "write_file": ToolTier.TIER_0_UTILITY,
    "list_dir": ToolTier.TIER_0_UTILITY,
    "document_inspect": ToolTier.TIER_1_COMPUTE,
    "image_analyze": ToolTier.TIER_2_VISION,
    "image_generate": ToolTier.TIER_3_CREATOR,
    "generate_reforge_report": ToolTier.TIER_0_UTILITY,
}

def get_tool_map(toolbox: ToolBox) -> Dict[str, Callable]:
    return {
        "read_file": toolbox.read_file,
        "write_file": toolbox.write_file,
        "list_dir": toolbox.list_dir,
        "document_inspect": toolbox.document_inspect,
        "image_analyze": toolbox.image_analyze,
        "image_generate": toolbox.image_generate,
        "create_issue": toolbox.create_issue,
        "update_issue_status": toolbox.update_issue_status,
        "request_excuse": toolbox.request_excuse,
        "archive_eval": toolbox.archive_eval,
        "promote_prompt": toolbox.promote_prompt,
        "generate_reforge_report": toolbox.generate_reforge_report,
    }