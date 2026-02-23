# tests/lsi/adapter.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

# Expect these modules to exist based on what you generated:
from orket.kernel.v1.state.lsi import LocalSovereignIndex
from orket.kernel.v1.state.promotion import promote_turn


@dataclass(frozen=True)
class StagedTurn:
    run_id: str
    turn_id: str
    staging_root: Path


class LsiAdapter:
    """
    Black-box adapter for scenario-driven tests.

    The tests should NOT care about internal folder layout beyond the public
    contract: staging vs committed, and the ability to stage triplets + deletions,
    then promote atomically.
    """

    def __init__(self, home: Path):
        self.home = home
        self.index_root = home / "index"
        self.runs_root = home / "runs"
        self.lsi = LocalSovereignIndex(home)

    # -----------------------
    # Run/Turn scaffolding
    # -----------------------

    def start_run(self, run_id: str) -> None:
        (self.runs_root / run_id).mkdir(parents=True, exist_ok=True)

    def stage_turn(self, run_id: str, turn_id: str) -> StagedTurn:
        staging_root = self.lsi.staging_turn_root(run_id, turn_id)
        staging_root.mkdir(parents=True, exist_ok=True)
        return StagedTurn(run_id=run_id, turn_id=turn_id, staging_root=staging_root)

    # -----------------------
    # Staging mutations
    # -----------------------

    def stage_triplet(
        self,
        run_id: str,
        turn_id: str,
        *,
        stem: str,
        dto_type: str | None,
        body: dict[str, Any],
        links: dict[str, Any],
        manifest: dict[str, Any],
    ) -> None:
        """
        Stage a complete triplet in the staging area.
        The LSI is responsible for canonicalization+digest+object storage.
        """
        self.lsi.stage_triplet(
            run_id=run_id,
            turn_id=turn_id,
            stem=stem,
            dto_type=dto_type,
            body=body,
            links=links,
            manifest=manifest,
        )

    def stage_deletions(self, run_id: str, turn_id: str, stems: Iterable[str]) -> None:
        """
        Deletion Option A (explicit list, minimal).
        """
        self.lsi.stage_deletions(run_id=run_id, turn_id=turn_id, stems=sorted(set(stems)))

    # -----------------------
    # Promotion
    # -----------------------

    def promote(self, run_id: str, turn_id: str) -> list[str]:
        """
        Promote staging -> committed atomically.
        Returns deterministic events emitted by promotion (incl I_REF_MULTISOURCE).
        """
        return promote_turn(self.home, run_id=run_id, turn_id=turn_id)

    # -----------------------
    # Readback helpers
    # -----------------------

    def read_committed_triplet_record(self, stem: str) -> dict[str, Any]:
        return self.lsi.read_committed_triplet_record(stem)

    def try_read_committed_triplet_record(self, stem: str) -> dict[str, Any] | None:
        try:
            return self.read_committed_triplet_record(stem)
        except FileNotFoundError:
            return None

    def read_committed_ref_record(self, ref_type: str, ref_id: str) -> dict[str, Any]:
        return self.lsi.read_committed_ref_record(ref_type, ref_id)

    def committed_snapshot_bytes(self) -> bytes:
        """
        Used for atomic flip tests: take a deterministic snapshot of committed/.
        """
        return self.lsi.snapshot_committed_bytes()
