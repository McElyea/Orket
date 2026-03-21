from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional

from .leak_policy import (
    DEFAULT_CODE_LEAK_PATTERNS,
    DEFAULT_LEAK_GATE_MODE,
    LeakDetection,
    detect_code_leak,
)
from .metrics import diff_ratio, jaccard_sim
from .parsers import normalize_newlines, parse_architect, parse_auditor
from .semantic_validity import evaluate_semantic_validity


@dataclass
class ReactorConfig:
    max_rounds: int = 8
    diff_floor_pct: float = 0.05
    stable_rounds: int = 2
    shingle_k: int = 3
    margin: float = 0.02
    min_loop_sim: float = 0.65
    code_leak_patterns: List[str] = field(default_factory=lambda: list(DEFAULT_CODE_LEAK_PATTERNS))
    leak_gate_mode: str = DEFAULT_LEAK_GATE_MODE

    def as_dict(self) -> Dict[str, Any]:
        return {
            "max_rounds": int(self.max_rounds),
            "diff_floor_pct": float(self.diff_floor_pct),
            "stable_rounds": int(self.stable_rounds),
            "shingle_k": int(self.shingle_k),
            "margin": float(self.margin),
            "min_loop_sim": float(self.min_loop_sim),
            "code_leak_patterns": list(self.code_leak_patterns),
            "leak_gate_mode": str(self.leak_gate_mode),
        }


@dataclass(frozen=True)
class ReactorState:
    # `history_v` is the truthful attempt log. `valid_history_v` is the convergence trace.
    history_v: List[str] = field(default_factory=list)
    history_rounds: List[Dict[str, Any]] = field(default_factory=list)
    stable_count: int = 0
    stop_reason: Optional[str] = None
    valid_history_v: List[str] = field(default_factory=list)
    invalid_history_v: List[str] = field(default_factory=list)
    invalid_stable_count: int = 0


def check_code_leak(text: str, patterns: List[str]) -> bool:
    """Delegate to the authoritative leak detector used by `run_round`."""
    detection = detect_code_leak(
        architect_raw=text,
        auditor_raw="",
        mode=DEFAULT_LEAK_GATE_MODE,
        patterns=patterns or None,
    )
    return detection.hard_leak


def _base_metrics(*, n: int, code_leak_hit: bool, stable_count: int) -> Dict[str, Any]:
    return {
        "code_leak_hit": bool(code_leak_hit),
        "n": int(n),
        "diff_ratio": None,
        "sim_prev": None,
        "sim_loop": None,
        "stable_count": int(stable_count),
    }


def _state_with_record(
    state: ReactorState,
    *,
    record: Dict[str, Any],
    stop_reason: Optional[str],
    history_v: List[str] | None = None,
    stable_count: int | None = None,
    valid_history_v: List[str] | None = None,
    invalid_history_v: List[str] | None = None,
    invalid_stable_count: int | None = None,
) -> ReactorState:
    return replace(
        state,
        history_v=list(state.history_v if history_v is None else history_v),
        history_rounds=[*state.history_rounds, record],
        stable_count=state.stable_count if stable_count is None else int(stable_count),
        stop_reason=stop_reason,
        valid_history_v=list(state.valid_history_v if valid_history_v is None else valid_history_v),
        invalid_history_v=list(state.invalid_history_v if invalid_history_v is None else invalid_history_v),
        invalid_stable_count=(
            state.invalid_stable_count if invalid_stable_count is None else int(invalid_stable_count)
        ),
    )


def _last_architect_data(state: ReactorState) -> Dict[str, Any] | None:
    for row in reversed(state.history_rounds):
        if str(row.get("validity_verdict") or "").strip().lower() != "valid":
            continue
        payload = row.get("architect_parsed")
        if isinstance(payload, dict):
            return dict(payload)
    return None


def _advance_history_metrics(
    *,
    history: List[str],
    prior_stable_count: int,
    cfg: ReactorConfig,
    metrics: Dict[str, Any],
    stable_count_key: str = "stable_count",
) -> tuple[int, bool, bool]:
    next_stable_count = int(prior_stable_count)
    diff_hit = False
    circ_hit = False

    if len(history) >= 2:
        previous = history[-2]
        metrics["diff_ratio"] = diff_ratio(history[-1], previous)
        if metrics["diff_ratio"] < float(cfg.diff_floor_pct):
            next_stable_count += 1
        else:
            next_stable_count = 0
        metrics[stable_count_key] = int(next_stable_count)
        diff_hit = next_stable_count >= int(cfg.stable_rounds)

    if len(history) >= 3:
        sim_prev = jaccard_sim(history[-1], history[-2], int(cfg.shingle_k))
        sim_loop = jaccard_sim(history[-1], history[-3], int(cfg.shingle_k))
        metrics["sim_prev"] = sim_prev
        metrics["sim_loop"] = sim_loop
        circ_hit = sim_loop > (sim_prev + float(cfg.margin)) and sim_loop >= float(cfg.min_loop_sim)

    return next_stable_count, diff_hit, circ_hit


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

    leak_detection: LeakDetection = detect_code_leak(
        architect_raw=normalized_architect_raw,
        auditor_raw=normalized_auditor_raw,
        mode=str(cfg.leak_gate_mode or DEFAULT_LEAK_GATE_MODE),
        patterns=cfg.code_leak_patterns,
    )
    if leak_detection.hard_leak:
        record = {
            "round": round_idx,
            "run_config": run_config,
            "code_leak_gate_mode": str(cfg.leak_gate_mode or DEFAULT_LEAK_GATE_MODE),
            "architect_raw": normalized_architect_raw,
            "auditor_raw": normalized_auditor_raw,
            "architect_parsed": None,
            "auditor_parsed": None,
            "parse_errors": [],
            "metrics": _base_metrics(n=attempted_n, code_leak_hit=True, stable_count=state.stable_count),
            "stop_reason": "CODE_LEAK",
        }
        record.update(leak_detection.as_trace_fields())
        return _state_with_record(state, record=record, stop_reason="CODE_LEAK")

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
            "code_leak_gate_mode": str(cfg.leak_gate_mode or DEFAULT_LEAK_GATE_MODE),
            "architect_raw": normalized_architect_raw,
            "auditor_raw": normalized_auditor_raw,
            "architect_parsed": None,
            "auditor_parsed": None,
            "parse_errors": parse_errors,
            "metrics": _base_metrics(n=attempted_n, code_leak_hit=False, stable_count=state.stable_count),
            "stop_reason": "FORMAT_VIOLATION",
        }
        record.update(leak_detection.as_trace_fields())
        return _state_with_record(state, record=record, stop_reason="FORMAT_VIOLATION")

    architect_data = dict(architect_parse["data"])
    auditor_data = dict(auditor_parse["data"])
    semantic = evaluate_semantic_validity(
        architect_data=architect_data,
        auditor_data=auditor_data,
        previous_architect_data=_last_architect_data(state),
    )
    current_requirement = str(architect_data["requirement"])
    history_v = [*state.history_v, current_requirement]
    n = len(history_v)

    metrics = _base_metrics(n=n, code_leak_hit=False, stable_count=state.stable_count)
    metrics["counts_toward_convergence"] = semantic["validity_verdict"] == "valid"
    metrics["accepted_stable_count"] = int(state.stable_count)
    metrics["invalid_stable_count"] = int(state.invalid_stable_count)

    next_stable_count = state.stable_count
    next_invalid_stable_count = state.invalid_stable_count
    valid_history_v = list(state.valid_history_v)
    invalid_history_v = list(state.invalid_history_v)
    diff_hit = False
    circ_hit = False

    if semantic["validity_verdict"] == "valid":
        valid_history_v = [*state.valid_history_v, current_requirement]
        next_stable_count, diff_hit, circ_hit = _advance_history_metrics(
            history=valid_history_v,
            prior_stable_count=state.stable_count,
            cfg=cfg,
            metrics=metrics,
        )
        next_invalid_stable_count = 0
        metrics["accepted_stable_count"] = int(next_stable_count)
        metrics["invalid_stable_count"] = 0
    else:
        next_stable_count = 0
        metrics["stable_count"] = 0
        metrics["accepted_stable_count"] = 0
        invalid_history_v = [*state.invalid_history_v, current_requirement]
        next_invalid_stable_count, diff_hit, circ_hit = _advance_history_metrics(
            history=invalid_history_v,
            prior_stable_count=state.invalid_stable_count,
            cfg=cfg,
            metrics=metrics,
            stable_count_key="invalid_stable_count",
        )
        metrics["invalid_stable_count"] = int(next_invalid_stable_count)

    # `max_rounds` is an attempt budget for the live loop, so invalid rounds count too.
    max_hit = n == int(cfg.max_rounds)
    stop_reason: Optional[str] = None
    if semantic["validity_verdict"] == "valid":
        if circ_hit:
            stop_reason = "LOOP_DETECTED"
        elif diff_hit:
            stop_reason = "STABLE_DIFF_FLOOR"
        elif max_hit:
            stop_reason = "MAX_ROUNDS"
    else:
        invalid_terminal = circ_hit or diff_hit or max_hit
        if semantic["pending_decision_count"] > 0 and invalid_terminal:
            stop_reason = "UNRESOLVED_DECISIONS"
        elif invalid_terminal:
            stop_reason = "INVALID_CONVERGENCE"

    record = {
        "round": round_idx,
        "run_config": run_config,
        "code_leak_gate_mode": str(cfg.leak_gate_mode or DEFAULT_LEAK_GATE_MODE),
        "architect_raw": normalized_architect_raw,
        "auditor_raw": normalized_auditor_raw,
        "architect_parsed": architect_data,
        "auditor_parsed": auditor_data,
        "parse_errors": [],
        "metrics": metrics,
        "validity_verdict": semantic["validity_verdict"],
        "semantic_failures": semantic["semantic_failures"],
        "pending_decision_count": semantic["pending_decision_count"],
        "pending_decisions": semantic["pending_decisions"],
        "contradiction_count": semantic["contradiction_count"],
        "contradiction_hits": semantic["contradiction_hits"],
        "constraint_demotion_violations": semantic["constraint_demotion_violations"],
        "required_constraint_regressions": semantic["required_constraint_regressions"],
        "repair_classes": semantic["repair_classes"],
        "patch_classes": semantic["patch_classes"],
        "stop_reason": stop_reason,
    }
    record.update(leak_detection.as_trace_fields())
    return _state_with_record(
        state,
        record=record,
        stop_reason=stop_reason,
        history_v=history_v,
        stable_count=next_stable_count,
        valid_history_v=valid_history_v,
        invalid_history_v=invalid_history_v,
        invalid_stable_count=next_invalid_stable_count,
    )
