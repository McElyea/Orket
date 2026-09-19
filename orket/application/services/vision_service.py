"""Captured image command admission and owned inference/publication lifetime."""
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.tools.families.vision import VisionTools


@dataclass(frozen=True)
class VisionService:
    root: Path
    references: tuple[Path, ...]
    model_id: str
    _adapter: VisionTools = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        if not self.root.is_absolute() or any(not path.is_absolute() for path in self.references):
            raise ValueError("E_VISION_ABSOLUTE_ROOT_REQUIRED")
        if not isinstance(self.model_id, str) or not self.model_id.strip():
            raise ValueError("E_VISION_MODEL_REQUIRED")
        object.__setattr__(self, "references", tuple(self.references))
        object.__setattr__(self, "_adapter", VisionTools(self.root, list(self.references), model_id=self.model_id))

    async def image_generate(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        captured = deepcopy(args)
        if not isinstance(captured.get("prompt"), str) or not captured["prompt"].strip():
            return {"ok": False, "error": "E_VISION_PROMPT_REQUIRED"}
        return await run_owned_thread(lambda: self._adapter.image_generate(captured), label="image-generation")

    async def image_analyze(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._adapter.image_analyze(args)
