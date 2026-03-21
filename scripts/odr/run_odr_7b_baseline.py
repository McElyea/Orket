"""
scripts/odr/run_odr_7b_baseline.py

Run the ODR role matrix against small (7B-and-under) model pairs using the same
refinement scenarios as the published 14B benchmarks. Produces an output file that
is structurally compatible with the existing arbiter and index generators, so it
can be slotted directly into the published benchmark pipeline.

Motivation
----------
All published ODR runs used 14B+ models on a 4090 with 24GB VRAM. This script
establishes the first baseline for whether small models can operate the ODR loop
at all — and if so, at what quality level. Results feed the single-vs-coordinated
comparison in run_odr_single_vs_coordinated.py.

Key differences from run_odr_live_role_matrix.py
-------------------------------------------------
- Default model list is 7B-and-under only
- Default round budget is 5 (not 8) — 7B models fail or converge faster
- Default timeout is 120s (not 180s)
- Captures additional 7B-specific diagnostics:
    - FORMAT_VIOLATION rate (7B models frequently miss headers)
    - CODE_LEAK rate per round (coding models leak code into requirements)
    - Empty-requirement rate (model produces a REQUIREMENT section with no text)
    - Mean rounds-to-stop across scenarios
- Writes a summary block at the end of the output for quick scanning

Usage
-----
    python scripts/odr/run_odr_7b_baseline.py \\
        --architect-models qwen2.5-coder:7b \\
        --auditor-models qwen2.5:7b \\
        --rounds 5 \\
        --out benchmarks/results/odr/odr_7b_baseline.json

    # Run all default 7B pairs against all refinement scenarios:
    python scripts/odr/run_odr_7b_baseline.py

Environment variables
---------------------
    ORKET_LLM_PROVIDER        ollama (default) | openai_compat | lmstudio
    ORKET_LLM_OLLAMA_HOST     Ollama base URL (default: http://localhost:11434)
    ORKET_LLM_TEMPERATURE     Override temperature for all calls
    ORKET_BENCH_SEED          Override seed for determinism
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.kernel.v1.odr.core import (  # noqa: E402
    DEFAULT_CODE_LEAK_PATTERNS,
    ReactorConfig,
    ReactorState,
    run_round,
)
from orket.kernel.v1.odr.metrics import diff_ratio  # noqa: E402
from orket.runtime.defaults import DEFAULT_LOCAL_MODEL  # noqa: E402
from scripts.odr.model_runtime_control import complete_with_transient_provider  # noqa: E402

# ---------------------------------------------------------------------------
# Defaults tuned for 7B models
# ---------------------------------------------------------------------------

DEFAULT_7B_ARCHITECTS = [
    DEFAULT_LOCAL_MODEL,
    "qwen2.5:7b",
]

DEFAULT_7B_AUDITORS = [
    "qwen2.5:7b",
    "llama3.2:3b",
]

SCENARIO_ROOT = REPO_ROOT / "tests" / "kernel" / "v1" / "vectors" / "odr" / "refinement"

# 7B models tend to stop (or fail) within 3-4 rounds. 5 is generous but avoids
# the situation where a confused model loops forever on MAX_ROUNDS=8.
DEFAULT_ROUNDS = 5
DEFAULT_MAX_ROUNDS = 5
DEFAULT_TEMPERATURE = 0.1
DEFAULT_TIMEOUT = 120


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Pairing:
    architect: str
    auditor: str


@dataclass
class RoundDiagnostics:
    """Per-round classification for 7B-specific summary stats."""

    round_index: int
    stop_reason: str | None
    code_leak_hit: bool
    format_violation: bool
    empty_requirement: bool
    diff_ratio_value: float | None
    architect_latency_ms: int
    auditor_latency_ms: int


@dataclass
class ScenarioDiagnostics:
    scenario_id: str
    stop_reason: str | None
    rounds_used: int
    rounds: list[RoundDiagnostics]
    converged: bool

    @property
    def code_leak_rounds(self) -> int:
        return sum(1 for r in self.rounds if r.code_leak_hit)

    @property
    def format_violation_rounds(self) -> int:
        return sum(1 for r in self.rounds if r.format_violation)

    @property
    def empty_requirement_rounds(self) -> int:
        return sum(1 for r in self.rounds if r.empty_requirement)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_list(raw: str) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def _load_scenarios() -> list[dict[str, Any]]:
    path = SCENARIO_ROOT / "scenarios.json"
    if not path.exists():
        raise FileNotFoundError(f"Scenario index not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_scenario_inputs(scenario: dict[str, Any]) -> dict[str, Any]:
    folder = SCENARIO_ROOT / str(scenario["path"])
    seed_file = str(scenario.get("seed_file") or "").strip()
    payload: dict[str, Any] = {
        "id": scenario["id"],
        "path": scenario["path"],
        "R0": (folder / "R0.md").read_text(encoding="utf-8"),
        "A0": json.loads((folder / "A0.json").read_text(encoding="utf-8")),
    }
    payload["seed"] = (
        json.loads((folder / seed_file).read_text(encoding="utf-8")) if seed_file else {}
    )
    return payload


def _scenario_brief(scenario_input: dict[str, Any]) -> str:
    issue_lines = [
        f"- id={issue.get('id')} status={issue.get('status')} "
        f"required_action={issue.get('required_action')}"
        for issue in scenario_input.get("A0", [])
    ]
    issue_block = "\n".join(issue_lines) if issue_lines else "- none"
    return (
        f"Scenario ID: {scenario_input.get('id')}\n"
        f"Seed decisions: {json.dumps(scenario_input.get('seed', {}), ensure_ascii=False)}\n"
        f"Initial requirement markdown follows.\n"
        f"{scenario_input.get('R0', '')}\n"
        f"Initial auditor issues:\n{issue_block}\n"
    )


def _architect_messages(
    *,
    scenario_input: dict[str, Any],
    current_requirement: str,
    prior_auditor_output: str,
    round_index: int,
) -> list[dict[str, str]]:
    system = (
        "You are the Architect role for requirement refinement.\n"
        "Return exactly these four sections, once each, in this exact order:\n"
        "### REQUIREMENT\n"
        "### CHANGELOG\n"
        "### ASSUMPTIONS\n"
        "### OPEN_QUESTIONS\n"
        "Rules:\n"
        "- No code fences or source code.\n"
        "- Keep statements concrete and testable.\n"
        "- Preserve prior accepted constraints unless explicitly replaced.\n"
        "- If a required numeric value is missing, use DECISION_REQUIRED wording.\n"
        "- REQUIREMENT must contain at least one sentence of plain English text.\n"
    )
    user = (
        f"{_scenario_brief(scenario_input)}\n"
        f"Round: {round_index}\n"
        "Current requirement under refinement:\n"
        f"{current_requirement}\n\n"
        "Prior auditor output (if any):\n"
        f"{prior_auditor_output or '- none'}\n"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _auditor_messages(
    *,
    scenario_input: dict[str, Any],
    architect_output: str,
    round_index: int,
) -> list[dict[str, str]]:
    system = (
        "You are the Auditor role for requirement refinement.\n"
        "Return exactly these four sections, once each, in this exact order:\n"
        "### CRITIQUE\n"
        "### PATCHES\n"
        "### EDGE_CASES\n"
        "### TEST_GAPS\n"
        "Rules:\n"
        "- No code fences or source code.\n"
        "- Be adversarial and specific.\n"
        "- Flag regressions, missing constraints, and hallucinated constants.\n"
        "- If the architect output contains code, flag it in CRITIQUE.\n"
        "- When a required field can be resolved from task context, propose the concrete value with [REWRITE].\n"
        "- Use [DECISION_REQUIRED] only when no reasonable default exists in the task context.\n"
    )
    user = (
        f"{_scenario_brief(scenario_input)}\n"
        f"Round: {round_index}\n"
        "Architect output to audit:\n"
        f"{architect_output}\n"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _is_empty_requirement(architect_parsed: dict[str, Any] | None) -> bool:
    if not isinstance(architect_parsed, dict):
        return True
    req = str(architect_parsed.get("requirement") or "").strip()
    return len(req) < 10


def _collect_ollama_version() -> str:
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return (result.stdout or result.stderr or "").strip().splitlines()[0] if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _collect_host_environment() -> dict[str, Any]:
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "arch": platform.machine(),
        "python_version": platform.python_version(),
        "ollama_version": _collect_ollama_version(),
        "llm_provider": str(os.getenv("ORKET_LLM_PROVIDER", "ollama")),
        "ollama_host": str(os.getenv("ORKET_LLM_OLLAMA_HOST", "http://localhost:11434")),
    }


# ---------------------------------------------------------------------------
# Core scenario runner
# ---------------------------------------------------------------------------


async def _run_scenario_live(
    *,
    scenario_input: dict[str, Any],
    architect_model: str,
    auditor_model: str,
    rounds: int,
    odr_cfg: ReactorConfig,
    temperature: float,
    timeout: int,
) -> tuple[dict[str, Any], ScenarioDiagnostics]:
    """
    Run one scenario through the ODR loop.

    Returns (full_round_record, diagnostics).
    """
    state = ReactorState()
    current_requirement = str(scenario_input.get("R0") or "")
    prior_auditor_output = ""
    round_rows: list[dict[str, Any]] = []
    diagnostics_rows: list[RoundDiagnostics] = []

    for round_index in range(1, rounds + 1):
        arch_messages = _architect_messages(
            scenario_input=scenario_input,
            current_requirement=current_requirement,
            prior_auditor_output=prior_auditor_output,
            round_index=round_index,
        )
        arch_resp, arch_latency_ms, arch_residency = await complete_with_transient_provider(
            model=architect_model,
            messages=arch_messages,
            temperature=temperature,
            timeout=timeout,
        )
        architect_raw = str(arch_resp.content or "").strip()

        aud_messages = _auditor_messages(
            scenario_input=scenario_input,
            architect_output=architect_raw,
            round_index=round_index,
        )
        aud_resp, aud_latency_ms, aud_residency = await complete_with_transient_provider(
            model=auditor_model,
            messages=aud_messages,
            temperature=temperature,
            timeout=timeout,
        )
        auditor_raw = str(aud_resp.content or "").strip()

        pre_count = len(state.history_rounds)
        state = run_round(state, architect_raw, auditor_raw, odr_cfg)
        trace = state.history_rounds[-1] if len(state.history_rounds) > pre_count else None

        metrics = (trace.get("metrics") or {}) if isinstance(trace, dict) else {}
        architect_parsed = (trace.get("architect_parsed")) if isinstance(trace, dict) else None
        stop_reason_this_round = str((trace or {}).get("stop_reason") or "")

        # 7B diagnostics
        code_leak_hit = bool(metrics.get("code_leak_hit")) if isinstance(metrics, dict) else False
        format_violation = stop_reason_this_round in {"FORMAT_VIOLATION", "SHAPE_VIOLATION"}
        empty_req = _is_empty_requirement(architect_parsed)

        dr_value: float | None = None
        if isinstance(metrics, dict) and metrics.get("diff_ratio") is not None:
            try:
                dr_value = float(metrics["diff_ratio"])
            except (TypeError, ValueError):
                pass

        diag = RoundDiagnostics(
            round_index=round_index,
            stop_reason=stop_reason_this_round or None,
            code_leak_hit=code_leak_hit,
            format_violation=format_violation,
            empty_requirement=empty_req,
            diff_ratio_value=dr_value,
            architect_latency_ms=arch_latency_ms,
            auditor_latency_ms=aud_latency_ms,
        )
        diagnostics_rows.append(diag)

        # Update running state for next round
        if isinstance(architect_parsed, dict):
            req_text = str(architect_parsed.get("requirement") or current_requirement)
            if req_text.strip():
                current_requirement = req_text
        prior_auditor_output = auditor_raw

        round_rows.append(
            {
                "round": round_index,
                "architect_messages": arch_messages,
                "auditor_messages": aud_messages,
                "architect_raw": architect_raw,
                "auditor_raw": auditor_raw,
                "architect_provider_raw": _json_safe(arch_resp.raw),
                "auditor_provider_raw": _json_safe(aud_resp.raw),
                "architect_model_residency": _json_safe(arch_residency),
                "auditor_model_residency": _json_safe(aud_residency),
                "odr_trace_record": _json_safe(trace),
                "state_stop_reason_after_round": state.stop_reason,
                "architect_latency_ms": arch_latency_ms,
                "auditor_latency_ms": aud_latency_ms,
            }
        )

        if state.stop_reason is not None:
            break

    converged = state.stop_reason in {"STABLE_DIFF_FLOOR", "LOOP_DETECTED"}
    scenario_diag = ScenarioDiagnostics(
        scenario_id=str(scenario_input.get("id") or ""),
        stop_reason=state.stop_reason,
        rounds_used=len(round_rows),
        rounds=diagnostics_rows,
        converged=converged,
    )

    result = {
        "scenario_id": scenario_input["id"],
        "original_input": scenario_input,
        "rounds": round_rows,
        "final_state": {
            "history_v": list(state.history_v),
            "history_round_count": len(state.history_rounds),
            "stable_count": state.stable_count,
            "stop_reason": state.stop_reason,
            "history_rounds": _json_safe(list(state.history_rounds)),
        },
    }
    return result, scenario_diag


# ---------------------------------------------------------------------------
# Pairing runner
# ---------------------------------------------------------------------------


async def _run_pairing(
    *,
    pairing: Pairing,
    scenario_inputs: list[dict[str, Any]],
    rounds: int,
    odr_cfg: ReactorConfig,
    temperature: float,
    timeout: int,
) -> tuple[dict[str, Any], list[ScenarioDiagnostics]]:
    scenarios_out: list[dict[str, Any]] = []
    diagnostics_out: list[ScenarioDiagnostics] = []
    started = datetime.now(UTC).isoformat()

    for scenario_input in scenario_inputs:
        scenario_id = str(scenario_input.get("id") or "?")
        print(f"    scenario={scenario_id} ...", flush=True)
        try:
            scenario_result, diag = await _run_scenario_live(
                scenario_input=scenario_input,
                architect_model=pairing.architect,
                auditor_model=pairing.auditor,
                rounds=rounds,
                odr_cfg=odr_cfg,
                temperature=temperature,
                timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"    scenario={scenario_id} ERROR: {exc}", flush=True)
            scenario_result = {
                "scenario_id": scenario_id,
                "original_input": scenario_input,
                "rounds": [],
                "final_state": {
                    "history_v": [],
                    "history_round_count": 0,
                    "stable_count": 0,
                    "stop_reason": f"RUNNER_ERROR:{type(exc).__name__}",
                    "history_rounds": [],
                },
                "runner_error": str(exc),
            }
            diag = ScenarioDiagnostics(
                scenario_id=scenario_id,
                stop_reason=f"RUNNER_ERROR:{type(exc).__name__}",
                rounds_used=0,
                rounds=[],
                converged=False,
            )
        else:
            stop = scenario_result["final_state"]["stop_reason"] or "NONE"
            rounds_used = scenario_result["final_state"]["history_round_count"]
            print(f"    scenario={scenario_id} stop_reason={stop} rounds={rounds_used}", flush=True)

        scenarios_out.append(scenario_result)
        diagnostics_out.append(diag)

    ended = datetime.now(UTC).isoformat()
    pairing_result = {
        "architect_model": pairing.architect,
        "auditor_model": pairing.auditor,
        "started_at": started,
        "ended_at": ended,
        "scenarios": scenarios_out,
    }
    return pairing_result, diagnostics_out


# ---------------------------------------------------------------------------
# 7B-specific summary builder
# ---------------------------------------------------------------------------


def _build_7b_summary(
    *,
    pairings: list[Pairing],
    all_diagnostics: list[list[ScenarioDiagnostics]],
) -> dict[str, Any]:
    """
    Produce a flat summary table that highlights 7B-specific failure modes.
    This is the primary artifact for quickly scanning whether small models can
    operate the ODR loop and where they break down.
    """
    rows = []
    for pairing, diag_list in zip(pairings, all_diagnostics):
        total_scenarios = len(diag_list)
        total_rounds = sum(d.rounds_used for d in diag_list)
        converged = sum(1 for d in diag_list if d.converged)
        code_leak_scenarios = sum(1 for d in diag_list if d.code_leak_rounds > 0)
        format_violation_scenarios = sum(1 for d in diag_list if d.format_violation_rounds > 0)
        empty_req_scenarios = sum(1 for d in diag_list if d.empty_requirement_rounds > 0)
        max_rounds_scenarios = sum(1 for d in diag_list if d.stop_reason == "MAX_ROUNDS")
        mean_rounds = (total_rounds / total_scenarios) if total_scenarios > 0 else 0.0

        stop_reasons: dict[str, int] = {}
        for d in diag_list:
            key = str(d.stop_reason or "NONE")
            stop_reasons[key] = stop_reasons.get(key, 0) + 1

        rows.append(
            {
                "architect_model": pairing.architect,
                "auditor_model": pairing.auditor,
                "total_scenarios": total_scenarios,
                "converged": converged,
                "convergence_rate": round(converged / total_scenarios, 4) if total_scenarios > 0 else 0.0,
                "mean_rounds_to_stop": round(mean_rounds, 2),
                "code_leak_scenarios": code_leak_scenarios,
                "code_leak_rate": round(code_leak_scenarios / total_scenarios, 4) if total_scenarios > 0 else 0.0,
                "format_violation_scenarios": format_violation_scenarios,
                "format_violation_rate": (
                    round(format_violation_scenarios / total_scenarios, 4) if total_scenarios > 0 else 0.0
                ),
                "empty_requirement_scenarios": empty_req_scenarios,
                "max_rounds_scenarios": max_rounds_scenarios,
                "stop_reason_distribution": stop_reasons,
            }
        )

    # Rank: most converged first, then fewest format violations, then fewest code leaks
    rows.sort(
        key=lambda r: (
            -r["convergence_rate"],
            r["format_violation_rate"],
            r["code_leak_rate"],
            r["mean_rounds_to_stop"],
        )
    )

    interpretation = _interpret_7b_results(rows)

    return {
        "summary_v": "7b_baseline.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "pairing_count": len(rows),
        "pairings": rows,
        "interpretation": interpretation,
    }


def _interpret_7b_results(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Produce a plain-language interpretation of the results for quick reading."""
    if not rows:
        return {"verdict": "NO_DATA", "failure_mode": "none", "dominant_stop_reason": "NONE"}

    best = rows[0]
    all_zero_convergence = all(r["convergence_rate"] == 0.0 for r in rows)
    high_code_leak = any(r["code_leak_rate"] > 0.5 for r in rows)
    high_format_violation = any(r["format_violation_rate"] > 0.5 for r in rows)
    stop_reason_totals: dict[str, int] = {}
    for row in rows:
        distribution = row.get("stop_reason_distribution") or {}
        if not isinstance(distribution, dict):
            continue
        for reason, count in distribution.items():
            key = str(reason or "NONE")
            try:
                stop_reason_totals[key] = stop_reason_totals.get(key, 0) + int(count)
            except (TypeError, ValueError):
                continue
    dominant_stop_reason = max(stop_reason_totals.items(), key=lambda item: item[1])[0] if stop_reason_totals else "NONE"

    if all_zero_convergence:
        verdict = "FAIL_NO_CONVERGENCE"
        if high_format_violation or dominant_stop_reason in {"FORMAT_VIOLATION", "SHAPE_VIOLATION"}:
            failure_mode = "format_instability"
            notes = [
                "No model pair achieved ODR convergence across any scenario.",
                "The dominant failure mode was format instability: 7B models did not reliably maintain the "
                "required REQUIREMENT/CHANGELOG/ASSUMPTIONS/OPEN_QUESTIONS structure across rounds.",
                "Recommended action: review FORMAT_VIOLATION rates and consider prompt hardening "
                "before attempting task-level workloads.",
            ]
        elif dominant_stop_reason == "UNRESOLVED_DECISIONS":
            failure_mode = "semantic_non_convergence_unresolved_decisions"
            notes = [
                "No model pair achieved ODR convergence across any scenario.",
                "The dominant failure mode was semantic non-convergence: runs ended with unresolved required "
                "decisions rather than structural format violations.",
                "Recommended action: inspect OPEN_QUESTIONS growth, contradiction hits, and requirement "
                "over-specification before attributing the failure to prompt formatting.",
            ]
        elif high_code_leak or dominant_stop_reason == "CODE_LEAK":
            failure_mode = "code_leak"
            notes = [
                "No model pair achieved ODR convergence across any scenario.",
                "The dominant failure mode was code leakage into requirement text rather than stable refinement.",
                "Recommended action: reduce coder-model leakage or switch the architect role to a "
                "general-purpose model before attempting task-level workloads.",
            ]
        else:
            failure_mode = f"non_convergence_{dominant_stop_reason.lower()}"
            notes = [
                "No model pair achieved ODR convergence across any scenario.",
                f"The dominant stop reason was {dominant_stop_reason}, indicating the failure mode was not "
                "uniformly explained by format instability alone.",
                "Recommended action: inspect the scenario-level stop reason distribution before drawing model "
                "capability conclusions from the zero-convergence result.",
            ]
    elif best["convergence_rate"] >= 0.6:
        verdict = "PASS_USABLE"
        failure_mode = "none"
        notes = [
            f"Best pair {best['architect_model']} / {best['auditor_model']} "
            f"converged on {int(best['convergence_rate'] * 100)}% of scenarios.",
            "Small models appear viable for ODR-coordinated tasks on these scenario types.",
        ]
    else:
        verdict = "PARTIAL_MIXED"
        failure_mode = "partial"
        notes = [
            f"Best pair achieved {int(best['convergence_rate'] * 100)}% convergence — "
            "usable but unreliable.",
            "Consider increasing round budget or relaxing diff_floor_pct before production use.",
        ]

    if high_code_leak:
        notes.append(
            "WARNING: High CODE_LEAK rate detected. Coding-specialized 7B models "
            "frequently produce source code in requirement text. Consider using a "
            "general-purpose model as architect rather than a coder model."
        )
    if high_format_violation:
        notes.append(
            "WARNING: High FORMAT_VIOLATION rate detected. Models are missing required "
            "section headers. Consider adding a single-turn format-correction pre-pass "
            "before entering the ODR loop."
        )

    return {
        "verdict": verdict,
        "failure_mode": failure_mode,
        "dominant_stop_reason": dominant_stop_reason,
        "best_pairing": {
            "architect": best["architect_model"],
            "auditor": best["auditor_model"],
            "convergence_rate": best["convergence_rate"],
        },
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


async def _main_async(args: argparse.Namespace) -> int:
    architects = _parse_list(args.architect_models)
    auditors = _parse_list(args.auditor_models)

    if not architects:
        print("ERROR: No architect models specified.", file=sys.stderr)
        return 1
    if not auditors:
        print("ERROR: No auditor models specified.", file=sys.stderr)
        return 1

    scenarios = _load_scenarios()
    selected_ids = set(_parse_list(args.scenario_ids))
    if selected_ids:
        scenarios = [s for s in scenarios if str(s.get("id")) in selected_ids]
    if args.max_scenarios > 0:
        scenarios = scenarios[: args.max_scenarios]
    scenario_inputs = [_load_scenario_inputs(s) for s in scenarios]

    if not scenario_inputs:
        print("ERROR: No scenarios loaded.", file=sys.stderr)
        return 1

    pairings = [Pairing(a, b) for a, b in itertools.product(architects, auditors)]

    code_leak_patterns: list[str] | None = None
    if args.code_leak_patterns_json.strip():
        parsed_patterns = json.loads(args.code_leak_patterns_json)
        if isinstance(parsed_patterns, list):
            code_leak_patterns = [str(p) for p in parsed_patterns]

    odr_cfg = ReactorConfig(
        max_rounds=args.max_rounds,
        diff_floor_pct=args.diff_floor_pct,
        stable_rounds=args.stable_rounds,
        shingle_k=args.shingle_k,
        margin=args.margin,
        min_loop_sim=args.min_loop_sim,
        code_leak_patterns=(
            list(code_leak_patterns) if code_leak_patterns is not None else list(DEFAULT_CODE_LEAK_PATTERNS)
        ),
        leak_gate_mode=str(args.leak_gate_mode or "balanced_v1"),
    )

    print(f"[7B-ODR] architects={architects}", flush=True)
    print(f"[7B-ODR] auditors={auditors}", flush=True)
    print(f"[7B-ODR] scenarios={[s['id'] for s in scenarios]}", flush=True)
    print(f"[7B-ODR] rounds_per_scenario={args.rounds}  max_rounds={args.max_rounds}", flush=True)
    print(f"[7B-ODR] temperature={args.temperature}  timeout={args.timeout}s", flush=True)
    print(f"[7B-ODR] pairings={len(pairings)}", flush=True)
    print()

    pairing_results: list[dict[str, Any]] = []
    all_diagnostics: list[list[ScenarioDiagnostics]] = []

    run_started = datetime.now(UTC).isoformat()
    wall_start = time.perf_counter()

    for idx, pairing in enumerate(pairings, start=1):
        print(
            f"[{idx}/{len(pairings)}] architect={pairing.architect}  auditor={pairing.auditor}",
            flush=True,
        )
        row, diag_list = await _run_pairing(
            pairing=pairing,
            scenario_inputs=scenario_inputs,
            rounds=args.rounds,
            odr_cfg=odr_cfg,
            temperature=args.temperature,
            timeout=args.timeout,
        )
        pairing_results.append(row)
        all_diagnostics.append(diag_list)
        print(f"  -> pairing complete", flush=True)

    run_ended = datetime.now(UTC).isoformat()
    duration_ms = int((time.perf_counter() - wall_start) * 1000)

    summary = _build_7b_summary(pairings=pairings, all_diagnostics=all_diagnostics)

    payload = {
        "run_v": "7b_baseline.v1",
        "generated_at": run_started,
        "ended_at": run_ended,
        "duration_ms": duration_ms,
        "config": {
            "architect_models": architects,
            "auditor_models": auditors,
            "scenario_ids": [s.get("id") for s in scenarios],
            "rounds": args.rounds,
            "odr_config": odr_cfg.as_dict(),
            "temperature": args.temperature,
            "timeout": args.timeout,
        },
        "environment": _collect_host_environment(),
        "results": pairing_results,
        "summary": summary,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(_json_safe(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"\n[7B-ODR] Wrote {out_path}", flush=True)

    # Print quick result table to stdout
    print("\n--- 7B Baseline Summary ---", flush=True)
    for row in summary["pairings"]:
        print(
            f"  {row['architect_model']} / {row['auditor_model']}"
            f"  converged={row['converged']}/{row['total_scenarios']}"
            f"  ({int(row['convergence_rate'] * 100)}%)"
            f"  code_leak={int(row['code_leak_rate'] * 100)}%"
            f"  format_violation={int(row['format_violation_rate'] * 100)}%"
            f"  mean_rounds={row['mean_rounds_to_stop']}",
            flush=True,
        )
    print(f"\n  Verdict: {summary['interpretation']['verdict']}", flush=True)
    for note in summary["interpretation"]["notes"]:
        print(f"  - {note}", flush=True)

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the ODR role matrix against 7B-and-under model pairs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--architect-models",
        default=",".join(DEFAULT_7B_ARCHITECTS),
        help="Comma-separated list of architect model IDs.",
    )
    parser.add_argument(
        "--auditor-models",
        default=",".join(DEFAULT_7B_AUDITORS),
        help="Comma-separated list of auditor model IDs.",
    )
    parser.add_argument(
        "--scenario-ids",
        default="",
        help="Comma-separated scenario IDs from refinement/scenarios.json. Empty = all.",
    )
    parser.add_argument("--max-scenarios", type=int, default=0, help="Limit scenarios (0 = all).")
    parser.add_argument(
        "--rounds",
        type=int,
        default=DEFAULT_ROUNDS,
        help="Max live LLM rounds per scenario.",
    )
    parser.add_argument("--max-rounds", type=int, default=DEFAULT_MAX_ROUNDS)
    parser.add_argument("--diff-floor-pct", type=float, default=0.05)
    parser.add_argument("--stable-rounds", type=int, default=2)
    parser.add_argument("--shingle-k", type=int, default=3)
    parser.add_argument("--margin", type=float, default=0.02)
    parser.add_argument("--min-loop-sim", type=float, default=0.65)
    parser.add_argument(
        "--code-leak-patterns-json",
        default="",
        help="Optional JSON array override for leak regex patterns.",
    )
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--leak-gate-mode",
        choices=["strict", "balanced_v1"],
        default="balanced_v1",
    )
    parser.add_argument(
        "--out",
        default="benchmarks/results/odr/odr_7b_baseline.json",
        help="Output JSON path.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
