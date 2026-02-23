from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.kernel.v1.contracts import KernelResult
from orket.kernel.v1.state.lsi import LocalSovereignIndex
from orket.kernel.v1.state.promotion import promote_turn


class LSIAdapter:
    """
    Test-to-kernel bridge (black-box).
    """

    def __init__(self, tmp_path: Path):
        self.root = tmp_path
        self.lsi = LocalSovereignIndex(root=str(tmp_path))

    def stage(self, *, stem: str, body: dict[str, Any], links: dict[str, Any], run_id: str, turn_id: str) -> KernelResult:
        self.lsi.stage_triplet(
            run_id=run_id,
            turn_id=turn_id,
            stem=stem,
            body=body,
            links=links,
            manifest={},
        )
        return KernelResult.pass_()

    def validate(self, *, stem: str, run_id: str, turn_id: str) -> KernelResult:
        outcome, issues, events = self.lsi.validate_links_against_index(
            run_id=run_id,
            turn_id=turn_id,
            stem=stem,
        )
        return KernelResult(outcome=outcome, issues=issues, events=events)

    def promote(self, *, run_id: str, turn_id: str) -> KernelResult:
        result = promote_turn(root=str(self.root), run_id=run_id, turn_id=turn_id)
        return KernelResult(outcome=result.outcome, issues=result.issues, events=result.events)
