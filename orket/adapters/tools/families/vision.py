from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from orket.adapters.tools.families.base import BaseTools
from orket.logging import log_event
from orket.settings import get_setting


class VisionTools(BaseTools):
    def __init__(self, workspace_root: Path, references: list[Path]):
        super().__init__(workspace_root, references)
        self._image_pipeline: Any | None = None

    def image_analyze(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "ok": False,
            "error": (
                "Visual analysis tool not implemented. Image analysis requires a vision-capable model or secondary API."
            ),
        }

    def image_generate(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            path = self._resolve_safe_path(args.get("path", "generated.png"), write=True)
            if self._image_pipeline is None:
                try:
                    import torch
                    from diffusers import StableDiffusionPipeline
                except ImportError:
                    return {
                        "ok": False,
                        "error": "Dependencies missing: pip install torch diffusers transformers accelerate",
                    }

                model_id = get_setting("sd_model", "runwayml/stable-diffusion-v1-5")
                device = "cuda" if torch.cuda.is_available() else "cpu"
                dtype = torch.float16 if device == "cuda" else torch.float32

                log_event(
                    "vision_pipeline_loading",
                    {"model_id": model_id, "device": device},
                    workspace=self.workspace_root,
                )
                pipeline_cls = cast(Any, StableDiffusionPipeline)
                self._image_pipeline = pipeline_cls.from_pretrained(model_id, torch_dtype=dtype)
                self._image_pipeline.to(device)

            image = self._image_pipeline(args.get("prompt")).images[0]
            path.parent.mkdir(parents=True, exist_ok=True)
            image.save(path)
            return {"ok": True, "path": str(path)}
        except (ImportError, OSError, RuntimeError, ValueError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}
