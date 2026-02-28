from __future__ import annotations

from pathlib import Path
from typing import Protocol


class Optimizer(Protocol):
    def generate(
        self,
        *,
        baseline_pack: Path,
        mode: dict[str, object],
        seed: int,
        budget: int,
        out_dir: Path,
    ) -> list[Path]:
        """Generate candidate resolved packs."""

