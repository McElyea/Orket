from __future__ import annotations

import json
import shutil
from pathlib import Path


class NoopOptimizer:
    def generate(
        self,
        *,
        baseline_pack: Path,
        mode: dict[str, object],
        seed: int,
        budget: int,
        out_dir: Path,
    ) -> list[Path]:
        del mode, seed, budget
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / "0001_pack_resolved"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(baseline_pack, target)
        (target / "mutation.json").write_text(
            json.dumps({"kind": "noop", "description": "baseline candidate"}, indent=2) + "\n",
            encoding="utf-8",
        )
        return [target]

