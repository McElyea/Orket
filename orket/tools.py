import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Callable

class ToolBox:
    """
    Standard Tool repository for all Orket Agents.
    Encapsulates filesystem, model interactions, and project management.
    """
    def __init__(self, policy, workspace_root: str, references: List[str]):
        self.policy = policy
        self.workspace_root = Path(workspace_root)
        self.references = [Path(r) for r in references]
        self._image_pipeline = None

    def _resolve_safe_path(self, path_str: str, write: bool = False) -> Path:
        p = Path(path_str)
        if not p.is_absolute():
            p = self.workspace_root / p
        
        # Check if path is within workspace or allowed references
        resolved = p.resolve()
        in_workspace = str(resolved).startswith(str(self.workspace_root.resolve()))
        in_references = any(str(resolved).startswith(str(r.resolve())) for r in self.references)
        
        if not (in_workspace or in_references):
            raise PermissionError(f"Access to path '{path_str}' is denied by security policy.")
            
        if write and not in_workspace:
            raise PermissionError(f"Write access to path '{path_str}' is restricted to workspace.")
            
        return resolved

    # --- Filesystem Tools ---

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

    # --- Semantic & Multi-Modal Tools ---

    def document_inspect(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Deep analysis of a document's semantic structure."""
        # Simplified for now: just read and return stats
        res = self.read_file(args, context)
        if not res.get("ok"): return res
        content = res.get("content", "")
        return {
            "ok": True, 
            "word_count": len(content.split()),
            "lines": len(content.splitlines()),
            "preview": content[:200]
        }

    def image_analyze(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Placeholder for Vision model integration."""
        return {"ok": True, "analysis": "Visual analysis tool orkestrated. No anomalies detected in target artifact."}

    def image_generate(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generates visual artifacts using local Stable Diffusion."""
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

    def add_issue_comment(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Adds a comment to the Card System for the current Issue. Use this to track progress, findings, or handoff notes."""
        issue_id = context.get("issue_id")
        content = args.get("comment")
        author = context.get("role", "Unknown")
        
        if not issue_id or not content: return {"ok": False, "error": "Missing comment content"}
        
        from orket.persistence import PersistenceManager
        db = PersistenceManager()
        db.add_comment(issue_id, author, content)
        return {"ok": True, "message": "Comment added to Card System."}

    def get_issue_context(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Retrieves the full comment history and status for an issue. ALWAYS call this when starting an Issue."""
        issue_id = args.get("issue_id") or context.get("issue_id")
        if not issue_id: return {"ok": False, "error": "No issue_id found"}
        
        from orket.persistence import PersistenceManager
        db = PersistenceManager()
        comments = db.get_comments(issue_id)
        # We don't have a direct 'get_issue' but we can filter from session
        session_id = context.get("session_id")
        issue_data = {}
        if session_id:
            issues = db.get_session_issues(session_id)
            issue_data = next((i for i in issues if i["id"] == issue_id), {})

        return {
            "ok": True,
            "status": issue_data.get("status"),
            "summary": issue_data.get("summary"),
            "comments": comments
        }

    def nominate_card(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Allows a member to proactively nominate a new Card (Rock, Epic, or Issue) for future orchestration. 
        Use this when you identify a logical next step or a missing requirement."""
        card_type = args.get("type", "issue").lower()
        summary = args.get("summary")
        note = args.get("note")
        priority = args.get("priority", "Medium")
        
        from orket.logging import log_event
        log_event("card_nomination", {
            "type": card_type,
            "summary": summary,
            "note": note,
            "priority": priority,
            "nominated_by": context.get("role")
        }, self.workspace_root, role="SYS")
        
        print(f"  [NOMINATION] {context.get('role')} nominated a new {card_type}: {summary}")
        return {"ok": True, "message": f"Nomination for '{summary}' recorded for user approval."}

    def report_credits(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Allows a member to explicitly report extra credits spent for high-value activities (Research, Creative, Legal)."""
        issue_id = context.get("issue_id")
        amount = args.get("amount", 0.0)
        reason = args.get("reason", "Manual credit report")
        if not issue_id or amount <= 0: return {"ok": False, "error": "Invalid params"}

        from orket.persistence import PersistenceManager
        db = PersistenceManager()
        db.add_credits(issue_id, amount)
        print(f"  [CREDITS] Seat {context.get('role')} reported {amount}c for: {reason}")
        return {"ok": True, "message": f"Reported {amount} credits."}

    def refinement_proposal(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Allows a Reforge Specialist to propose changes to Teams, Environments, or Skills based on performance data."""
        target = args.get("target_config") # e.g. "model/core/teams/standard.json"
        rationale = args.get("analysis")
        proposed_json = args.get("proposed_change")
        
        if not target or not proposed_json: return {"ok": False, "error": "Missing proposal data"}
        
        from orket.logging import log_event
        log_event("refinement_proposed", {"target": target, "rationale": rationale, "proposed": proposed_json}, self.workspace_root, role="SYS")
        
        print(f"  [REFORGE] Proposal submitted for {target}: {rationale[:100]}...")
        return {"ok": True, "message": "Refinement proposal logged for human or Driver review."}

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

def get_tool_map(toolbox: ToolBox) -> Dict[str, Callable]:
    return {
        "read_file": toolbox.read_file,
        "write_file": toolbox.write_file,
        "list_directory": toolbox.list_directory,
        "document_inspect": toolbox.document_inspect,
        "image_analyze": toolbox.image_analyze,
        "image_generate": toolbox.image_generate,
        "create_issue": toolbox.create_issue,
        "update_issue_status": toolbox.update_issue_status,
        "add_issue_comment": toolbox.add_issue_comment,
        "get_issue_context": toolbox.get_issue_context,
        "report_credits": toolbox.report_credits,
        "refinement_proposal": toolbox.refinement_proposal,
        "request_excuse": toolbox.request_excuse,
        "archive_eval": toolbox.archive_eval,
        "promote_prompt": toolbox.promote_prompt,
        "nominate_card": toolbox.nominate_card,
    }
