from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class FailingCase:
    case_id: str
    severity: float
    hard: bool


@dataclass(frozen=True)
class EvalResult:
    score: float
    hard_fail_count: int
    soft_fail_count: int
    failing_cases: tuple[FailingCase, ...]
    report_json_path: Path
    report_md_path: Path


class EvalHarness(Protocol):
    def run(
        self,
        *,
        model_id: str,
        mode_id: str,
        pack_path: Path,
        suite_path: Path,
        out_dir: Path,
    ) -> EvalResult:
        ...

