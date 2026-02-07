# orket/tools.py
import json
import os
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

import fitz  # PyMuPDF
import docx
import ollama
from orket.hardware import ToolTier

# ------------------------------------------------------------
# Tool Implementation Core
# ------------------------------------------------------------

class ToolBox:
    """
    Centralized tool management.
    Handles security gating and path resolution per session.
    """
    def __init__(self, policy, workspace: str, references: List[str] = None):
        self.policy = policy
        self.workspace = Path(workspace).resolve()
        self.references = [Path(r).resolve() for r in (references or [])]
        self._image_pipeline = None

    def _resolve_safe_path(self, path_str: str, write: bool = False) -> Path:
        """
        Gated path resolution. 
        Ensures the path stays within allowed spaces.
        """
        p = Path(path_str)
        if not p.is_absolute():
            p = (self.workspace / p).resolve()
        else:
            p = p.resolve()

        # Final Security Gate: Check the policy
        if write:
            if not self.policy.can_write(str(p)):
                raise PermissionError(f"Security Violation: Write access denied to {p}")
        else:
            if not self.policy.can_read(str(p)):
                # If reading, also check reference spaces
                found_in_ref = False
                for ref in self.references:
                    if str(p).startswith(str(ref)):
                        found_in_ref = True
                        break
                if not found_in_ref:
                    raise PermissionError(f"Security Violation: Read access denied to {p}")
        
        return p

    # --- Tool Implementations ---

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
}

def get_tool_map(toolbox: ToolBox) -> Dict[str, Callable]:
    """Returns a map of tool names to their bound methods in the toolbox."""
    return {
        "read_file": toolbox.read_file,
        "write_file": toolbox.write_file,
        "list_dir": toolbox.list_dir,
        "document_inspect": toolbox.document_inspect,
        "image_analyze": toolbox.image_analyze,
        "image_generate": toolbox.image_generate,
    }
