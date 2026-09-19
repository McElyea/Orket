from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

from orket.adapters.storage.file_admission import require_regular_or_absent
from orket.adapters.storage.local_file_lock import NativeFileLocks
from orket.adapters.storage.verified_file import write_verified_bytes
from orket.adapters.tools.families.base import BaseTools
from orket.logging import log_event


class VisionTools(BaseTools):
    """Blocking inference adapter; the application retains its worker and supplied model."""

    side_effecting = True

    def __init__(self, workspace_root: Path, references: list[Path], *, model_id: str):
        super().__init__(workspace_root, references)
        self.model_id = model_id
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
            if path == self.workspace_root.resolve():
                raise ValueError("E_VISION_OUTPUT_FILE_REQUIRED")
            locks = NativeFileLocks(self.workspace_root.resolve(), suffix=".vision-locks", error_prefix="E_VISION",
                                    empty_key_error="E_VISION_LOCK_KEY")
            with locks.hold_sync("image-generation"):
                require_regular_or_absent(path, error_code="E_VISION_OUTPUT_NOT_REGULAR")
                self._generate(path, args["prompt"])
            return {"ok": True, "path": str(path)}
        except ImportError:
            return {"ok": False, "error": "Dependencies missing: pip install torch diffusers transformers accelerate"}
        except (OSError, RuntimeError, ValueError, TypeError, KeyError, IndexError) as exc:
            return {"ok": False, "error": str(exc)}

    def _generate(self, path: Path, prompt: str) -> None:
        if self._image_pipeline is None:
            self._image_pipeline = self._load_pipeline()
        image = self._image_pipeline(prompt).images[0]
        path.parent.mkdir(parents=True, exist_ok=True)
        # Preserve the encoder's filename/format behavior without exposing a partial destination.
        with TemporaryDirectory(prefix=".vision-", dir=path.parent) as directory:
            encoded = Path(directory) / path.name
            image.save(encoded)
            payload = encoded.read_bytes()
            if not payload:
                raise ValueError("E_VISION_IMAGE_EMPTY")
            write_verified_bytes(path, payload, error_code="E_VISION_IMAGE_UNVERIFIED")

    def _load_pipeline(self):
        import torch
        from diffusers import StableDiffusionPipeline

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32
        log_event("vision_pipeline_loading", {"model_id": self.model_id, "device": device}, workspace=self.workspace_root)
        pipeline = cast(Any, StableDiffusionPipeline).from_pretrained(self.model_id, torch_dtype=dtype)
        pipeline.to(device)
        return pipeline
