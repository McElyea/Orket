from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .metrics import diff_ratio, jaccard_sim
from .parsers import normalize_newlines, parse_architect, parse_auditor


DEFAULT_CODE_LEAK_PATTERNS = [
    r"(?s)```.*?```",
    r"\b(def|class|import|fn|let|const|interface|type)\b",
    r"\b(npm|pip|cargo|docker|venv|node_modules)\b",
]


@dataclass
class ReactorConfig:
    max_rounds: int = 8
    diff_floor_pct: float = 0.05
    stable_rounds: int = 2
    shingle_k: int = 3
    margin: float = 0.02
    min_loop_sim: float = 0.65
    code_leak_patterns: List[str] = field(default_factory=lambda: list(DEFAULT_CODE_LEAK_PATTERNS))

    def as_dict(self) -> Dict[str, Any]:
        return {
            "max_rounds": int(self.max_rounds),
            "diff_floor_pct": float(self.diff_floor_pct),
            "stable_rounds": int(self.stable_rounds),
            "shingle_k": int(self.shingle_k),
            "margin": float(self.margin),
            "min_loop_sim": float(self.min_loop_sim),
            "code_leak_patterns": list(self.code_leak_patterns),
        }


@dataclass
class ReactorState:
    history_v: List[str] = field(default_factory=list)
    history_rounds: List[Dict[str, Any]] = field(default_factory=list)
    stable_count: int = 0
    stop_reason: Optional[str] = None


def check_code_leak(text: str, patterns: List[str]) -> bool:
    normalized = normalize_newlines(text)
    for pattern in patterns:
        if re.search(pattern, normalized) is not None:
            return True
    return False


def _base_metrics(*, n: int, code_leak_hit: bool, stable_count: int) -> Dict[str, Any]:
    return {
        "code_leak_hit": bool(code_leak_hit),
        "n": int(n),
        "diff_ratio": None,
        "sim_prev": None,
        "sim_loop": None,
        "stable_count": int(stable_count),
    }


def run_round(
    state: ReactorState,
    architect_raw: str,
    auditor_raw: str,
    cfg: ReactorConfig | None = None,
) -> ReactorState:
    cfg = cfg or ReactorConfig()
    if state.stop_reason is not None:
        return state

    normalized_architect_raw = normalize_newlines(architect_raw)
    normalized_auditor_raw = normalize_newlines(auditor_raw)
    round_idx = len(state.history_rounds) + 1
    attempted_n = len(state.history_v) + 1
    run_config = cfg.as_dict()

    code_leak_hit = check_code_leak(normalized_architect_raw, cfg.code_leak_patterns) or check_code_leak(
        normalized_auditor_raw,
        cfg.code_leak_patterns,
    )
    if code_leak_hit:
        record = {
            "round": round_idx,
            "run_config": run_config,
            "architect_raw": normalized_architect_raw,
            "auditor_raw": normalized_auditor_raw,
            "architect_parsed": None,
            "auditor_parsed": None,
            "parse_errors": [],
            "metrics": _base_metrics(n=attempted_n, code_leak_hit=True, stable_count=state.stable_count),
            "stop_reason": "CODE_LEAK",
        }
        state.history_rounds.append(record)
        state.stop_reason = "CODE_LEAK"
        return state

    architect_parse = parse_architect(normalized_architect_raw)
    auditor_parse = parse_auditor(normalized_auditor_raw)
    parse_errors: List[Dict[str, str]] = []
    if not architect_parse["ok"]:
        parse_errors.append(
            {
                "source": "architect",
                "code": str(architect_parse["error"]["code"]),
                "message": str(architect_parse["error"]["message"]),
            }
        )
    if not auditor_parse["ok"]:
        parse_errors.append(
            {
                "source": "auditor",
                "code": str(auditor_parse["error"]["code"]),
                "message": str(auditor_parse["error"]["message"]),
            }
        )
    if parse_errors:
        record = {
            "round": round_idx,
            "run_config": run_config,
            "architect_raw": normalized_architect_raw,
            "auditor_raw": normalized_auditor_raw,
            "architect_parsed": None,
            "auditor_parsed": None,
            "parse_errors": parse_errors,
            "metrics": _base_metrics(n=attempted_n, code_leak_hit=False, stable_count=state.stable_count),
            "stop_reason": "SHAPE_VIOLATION",
        }
        state.history_rounds.append(record)
        state.stop_reason = "SHAPE_VIOLATION"
        return state

    architect_data = dict(architect_parse["data"])
    auditor_data = dict(auditor_parse["data"])
    current_requirement = str(architect_data["requirement"])
    state.history_v.append(current_requirement)
    n = len(state.history_v)

    metrics = _base_metrics(n=n, code_leak_hit=False, stable_count=state.stable_count)

    diff_hit = False
    if n >= 2:
        prev_requirement = state.history_v[-2]
        metrics["diff_ratio"] = diff_ratio(current_requirement, prev_requirement)
        if metrics["diff_ratio"] < float(cfg.diff_floor_pct):
            state.stable_count += 1
        else:
            state.stable_count = 0
        metrics["stable_count"] = int(state.stable_count)
        diff_hit = state.stable_count >= int(cfg.stable_rounds)

    circ_hit = False
    if n >= 3:
        sim_prev = jaccard_sim(state.history_v[-1], state.history_v[-2], int(cfg.shingle_k))
        sim_loop = jaccard_sim(state.history_v[-1], state.history_v[-3], int(cfg.shingle_k))
        metrics["sim_prev"] = sim_prev
        metrics["sim_loop"] = sim_loop
        circ_hit = sim_loop > (sim_prev + float(cfg.margin)) and sim_loop >= float(cfg.min_loop_sim)

    max_hit = n == int(cfg.max_rounds)
    stop_reason: Optional[str] = None
    if max_hit:
        stop_reason = "MAX_ROUNDS"
    elif diff_hit:
        stop_reason = "DIFF_FLOOR"
    elif circ_hit:
        stop_reason = "CIRCULARITY"

    record = {
        "round": round_idx,
        "run_config": run_config,
        "architect_raw": normalized_architect_raw,
        "auditor_raw": normalized_auditor_raw,
        "architect_parsed": architect_data,
        "auditor_parsed": auditor_data,
        "parse_errors": [],
        "metrics": metrics,
        "stop_reason": stop_reason,
    }
    state.history_rounds.append(record)
    if stop_reason is not None:
        state.stop_reason = stop_reason
    return state
