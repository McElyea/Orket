from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ModelAdapter(Protocol):
    def generate(
        self,
        *,
        model_id: str,
        mode_id: str,
        case_id: str,
        prompt: str,
        pack_digest: str,
        pack_path: Path,
    ) -> str:
        ...


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
