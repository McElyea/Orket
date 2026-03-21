"""
scripts/odr/run_odr_single_vs_coordinated.py

Compare single-shot model output against ODR-coordinated output for the same task.

This script is the primary hypothesis-testing instrument for the thesis:
    "Small models coordinated well can produce output comparable to larger models."

For each task, it runs two modes back-to-back:
    1. Single-shot: one call asking the architect model to produce a complete
       requirement specification without any auditor loop.
    2. Coordinated: the same model pair run through the full ODR loop.

Both modes get the same input and the same scenario context. The output is a
structured comparison artifact showing where and how the outputs diverge.

What "better" means here
------------------------
The comparison does NOT produce a scalar quality score — that requires a human
judge or a reference answer. Instead it produces measurable structural signals:

    - constraint_count: how many distinct constraints the requirement captures
    - decision_required_count: how many open decisions remain unresolved
    - word_count: length proxy (longer is not always better, but too short is a signal)
    - rounds_to_stop: how many rounds the ODR needed to converge
    - stop_reason: STABLE_DIFF_FLOOR (good), CODE_LEAK/FORMAT_VIOLATION (bad)
    - diff_ratio_final: how much the requirement changed between last two rounds
      (near 0 = stable, high = still drifting)
    - single_vs_odr_diff_ratio: structural similarity between single-shot output
      and the final ODR requirement (high = ODR didn't change much; low = ODR
      produced something meaningfully different)

These signals together tell you:
    - Did the ODR improve coverage? (constraint_count single vs coordinated)
    - Did the ODR resolve ambiguity? (decision_required_count)
    - Did the ODR stabilize the output? (stop_reason + diff_ratio_final)
    - Was there a meaningful difference? (single_vs_odr_diff_ratio)

Usage
-----
    # Quick smoke test — one model pair, all scenarios, 3 rounds max:
    python scripts/odr/run_odr_single_vs_coordinated.py \\
        --architect-model qwen2.5-coder:7b \\
        --auditor-model qwen2.5:7b \\
        --rounds 3 \\
        --out benchmarks/results/odr/single_vs_coordinated_7b.json

    # Full run with multiple model pairs:
    python scripts/odr/run_odr_single_vs_coordinated.py \\
        --architect-model qwen2.5-coder:7b,qwen2.5:7b \\
        --auditor-model qwen2.5:7b \\
        --rounds 5

    # Run against a specific scenario only:
    python scripts/odr/run_odr_single_vs_coordinated.py \\
        --architect-model qwen2.5-coder:7b \\
        --auditor-model qwen2.5:7b \\
        --scenario-ids contradiction

Environment variables
---------------------
    ORKET_LLM_PROVIDER        ollama (default) | openai_compat | lmstudio
    ORKET_LLM_OLLAMA_HOST     Ollama base URL
    ORKET_LLM_TEMPERATURE     Override temperature
    ORKET_BENCH_SEED          Override seed for determinism
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import re
import subprocess
import sys
import time
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
from orket.kernel.v1.odr.metrics import diff_ratio, jaccard_sim  # noqa: E402
from orket.runtime.defaults import DEFAULT_LOCAL_MODEL  # noqa: E402
from scripts.odr.model_runtime_control import complete_with_transient_provider  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCENARIO_ROOT = REPO_ROOT / "tests" / "kernel" / "v1" / "vectors" / "odr" / "refinement"

DEFAULT_ARCHITECT = DEFAULT_LOCAL_MODEL
DEFAULT_AUDITOR = "qwen2.5:7b"
DEFAULT_ROUNDS = 5
DEFAULT_TEMPERATURE = 0.1
DEFAULT_TIMEOUT = 120

# Requirement section markers used for structural analysis
_CONSTRAINT_VERBS = re.compile(
    r"\b(must|shall|will not|should not|must not|is required to|"
    r"is prohibited from|requires|enforces)\b",
    re.IGNORECASE,
)
_DECISION_REQUIRED = re.compile(r"DECISION_REQUIRED", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _single_shot_messages(
    *,
    scenario_brief: str,
    round_index: int = 1,
) -> list[dict[str, str]]:
    """
    Single-shot prompt: ask the architect to produce a complete requirement
    specification in one pass, with no auditor feedback.
    """
    system = (
        "You are a requirements architect.\n"
        "Produce a complete, well-structured requirement specification.\n"
        "Return exactly these four sections, once each, in this exact order:\n"
        "### REQUIREMENT\n"
        "### CHANGELOG\n"
        "### ASSUMPTIONS\n"
        "### OPEN_QUESTIONS\n"
        "Rules:\n"
        "- No code fences or source code.\n"
        "- Use DECISION_REQUIRED for any value you cannot determine from context.\n"
        "- REQUIREMENT must contain at least one concrete, testable constraint.\n"
        "- Be thorough — this is your only chance to get it right.\n"
    )
    user = (
        f"{scenario_brief}\n"
        f"Round: {round_index}\n"
        "Produce the complete requirement specification now.\n"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _architect_messages(
    *,
    scenario_brief: str,
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
        "- If a required value is missing, use DECISION_REQUIRED.\n"
        "- REQUIREMENT must contain at least one sentence of plain English text.\n"
    )
    user = (
        f"{scenario_brief}\n"
        f"Round: {round_index}\n"
        "Current requirement under refinement:\n"
        f"{current_requirement}\n\n"
        "Prior auditor output (if any):\n"
        f"{prior_auditor_output or '- none'}\n"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _auditor_messages(
    *,
    scenario_brief: str,
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
        f"{scenario_brief}\n"
        f"Round: {round_index}\n"
        "Architect output to audit:\n"
        f"{architect_output}\n"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


# ---------------------------------------------------------------------------
# Scenario loading helpers
# ---------------------------------------------------------------------------


def _load_scenarios() -> list[dict[str, Any]]:
    path = SCENARIO_ROOT / "scenarios.json"
    if not path.exists():
        raise FileNotFoundError(f"Scenario index not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_scenario_inputs(scenario: dict[str, Any]) -> dict[str, Any]:
    folder = SCENARIO_ROOT / str(scenario["path"])
    seed_file = str(scenario.get("seed_file") or "").strip()
    return {
        "id": scenario["id"],
        "path": scenario["path"],
        "R0": (folder / "R0.md").read_text(encoding="utf-8"),
        "A0": json.loads((folder / "A0.json").read_text(encoding="utf-8")),
        "seed": json.loads((folder / seed_file).read_text(encoding="utf-8")) if seed_file else {},
    }


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


# ---------------------------------------------------------------------------
# Structural analysis helpers
# ---------------------------------------------------------------------------


def _extract_requirement_text(raw_response: str) -> str:
    """
    Extract the text under the ### REQUIREMENT section from a raw model response.
    Returns the full section text, or the full response if parsing fails.
    """
    lines = raw_response.splitlines()
    in_requirement = False
    requirement_lines: list[str] = []
    for line in lines:
        stripped = line.strip().lower()
        if stripped == "### requirement":
            in_requirement = True
            continue
        if in_requirement and stripped.startswith("### "):
            break
        if in_requirement:
            requirement_lines.append(line)
    result = "\n".join(requirement_lines).strip()
    return result if result else raw_response.strip()


def _analyze_requirement(text: str) -> dict[str, Any]:
    """
    Produce structural signals from a requirement text.
    These are heuristic proxies, not quality scores.
    """
    word_count = len(text.split())
    constraint_count = len(_CONSTRAINT_VERBS.findall(text))
    decision_required_count = len(_DECISION_REQUIRED.findall(text))
    sentence_count = len([s for s in re.split(r"[.!?]\s+", text) if s.strip()])
    has_numeric_value = bool(re.search(r"\b\d+\b", text))

    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "constraint_count": constraint_count,
        "decision_required_count": decision_required_count,
        "has_numeric_value": has_numeric_value,
        "is_empty": word_count < 5,
    }


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


# ---------------------------------------------------------------------------
# Single-shot runner
# ---------------------------------------------------------------------------


async def _run_single_shot(
    *,
    scenario_input: dict[str, Any],
    architect_model: str,
    temperature: float,
    timeout: int,
) -> dict[str, Any]:
    """
    Run one single-shot call for a scenario.
    No auditor, no loop — just one architect response.
    """
    brief = _scenario_brief(scenario_input)
    messages = _single_shot_messages(scenario_brief=brief)

    resp, latency_ms, residency_release = await complete_with_transient_provider(
        model=architect_model,
        messages=messages,
        temperature=temperature,
        timeout=timeout,
    )
    raw_output = str(resp.content or "").strip()

    requirement_text = _extract_requirement_text(raw_output)
    analysis = _analyze_requirement(requirement_text)

    return {
        "mode": "single_shot",
        "scenario_id": scenario_input["id"],
        "messages": messages,
        "raw_output": raw_output,
        "requirement_text": requirement_text,
        "analysis": analysis,
        "latency_ms": latency_ms,
        "provider_raw": _json_safe(resp.raw),
        "model_residency": _json_safe(residency_release),
    }


# ---------------------------------------------------------------------------
# Coordinated (ODR) runner
# ---------------------------------------------------------------------------


async def _run_coordinated(
    *,
    scenario_input: dict[str, Any],
    architect_model: str,
    auditor_model: str,
    rounds: int,
    odr_cfg: ReactorConfig,
    temperature: float,
    timeout: int,
) -> dict[str, Any]:
    """
    Run the full ODR loop for a scenario.
    Returns the final requirement text, ODR state, and per-round traces.
    """
    brief = _scenario_brief(scenario_input)
    state = ReactorState()
    current_requirement = str(scenario_input.get("R0") or "")
    prior_auditor_output = ""
    round_rows: list[dict[str, Any]] = []
    total_latency_ms = 0

    for round_index in range(1, rounds + 1):
        arch_msgs = _architect_messages(
            scenario_brief=brief,
            current_requirement=current_requirement,
            prior_auditor_output=prior_auditor_output,
            round_index=round_index,
        )
        arch_resp, arch_latency_ms, arch_residency = await complete_with_transient_provider(
            model=architect_model,
            messages=arch_msgs,
            temperature=temperature,
            timeout=timeout,
        )
        architect_raw = str(arch_resp.content or "").strip()

        aud_msgs = _auditor_messages(
            scenario_brief=brief,
            architect_output=architect_raw,
            round_index=round_index,
        )
        aud_resp, aud_latency_ms, aud_residency = await complete_with_transient_provider(
            model=auditor_model,
            messages=aud_msgs,
            temperature=temperature,
            timeout=timeout,
        )
        auditor_raw = str(aud_resp.content or "").strip()

        total_latency_ms += arch_latency_ms + aud_latency_ms

        pre_count = len(state.history_rounds)
        state = run_round(state, architect_raw, auditor_raw, odr_cfg)
        trace = state.history_rounds[-1] if len(state.history_rounds) > pre_count else None

        architect_parsed = (trace.get("architect_parsed") or {}) if isinstance(trace, dict) else {}
        req_text = str(architect_parsed.get("requirement") or "").strip()
        if req_text:
            current_requirement = req_text
        prior_auditor_output = auditor_raw

        round_rows.append(
            {
                "round": round_index,
                "architect_raw": architect_raw,
                "auditor_raw": auditor_raw,
                "odr_trace_record": _json_safe(trace),
                "state_stop_reason_after_round": state.stop_reason,
                "architect_latency_ms": arch_latency_ms,
                "auditor_latency_ms": aud_latency_ms,
                "architect_model_residency": _json_safe(arch_residency),
                "auditor_model_residency": _json_safe(aud_residency),
            }
        )

        if state.stop_reason is not None:
            break

    final_requirement_text = _extract_requirement_text(current_requirement)
    final_analysis = _analyze_requirement(final_requirement_text)

    # Measure how much the requirement changed between the last two history_v entries
    diff_ratio_final: float | None = None
    if len(state.history_v) >= 2:
        diff_ratio_final = diff_ratio(state.history_v[-1], state.history_v[-2])

    return {
        "mode": "coordinated",
        "scenario_id": scenario_input["id"],
        "rounds": round_rows,
        "final_requirement_text": final_requirement_text,
        "analysis": final_analysis,
        "total_latency_ms": total_latency_ms,
        "odr_final_state": {
            "history_v": list(state.history_v),
            "history_round_count": len(state.history_rounds),
            "stable_count": state.stable_count,
            "stop_reason": state.stop_reason,
            "diff_ratio_final": diff_ratio_final,
        },
    }


# ---------------------------------------------------------------------------
# Comparison builder
# ---------------------------------------------------------------------------


def _build_comparison(
    *,
    scenario_id: str,
    single: dict[str, Any],
    coordinated: dict[str, Any],
) -> dict[str, Any]:
    """
    Build a structured comparison between single-shot and coordinated output.
    This is the primary artifact for evaluating the hypothesis.
    """
    single_req = str(single.get("requirement_text") or "")
    odr_req = str(coordinated.get("final_requirement_text") or "")

    # Structural similarity between the two outputs
    single_vs_odr_diff_ratio = diff_ratio(single_req, odr_req) if single_req and odr_req else None
    single_vs_odr_jaccard = (
        jaccard_sim(single_req, odr_req, 3) if single_req and odr_req else None
    )

    single_analysis = single.get("analysis") or {}
    odr_analysis = coordinated.get("analysis") or {}
    odr_state = coordinated.get("odr_final_state") or {}

    # Delta signals — positive = ODR produced more of this
    constraint_delta = (
        int(odr_analysis.get("constraint_count") or 0) -
        int(single_analysis.get("constraint_count") or 0)
    )
    decision_required_delta = (
        int(odr_analysis.get("decision_required_count") or 0) -
        int(single_analysis.get("decision_required_count") or 0)
    )
    word_count_delta = (
        int(odr_analysis.get("word_count") or 0) -
        int(single_analysis.get("word_count") or 0)
    )

    # Interpretation of deltas
    odr_stop_reason = str(odr_state.get("stop_reason") or "NONE")
    odr_converged = odr_stop_reason in {"STABLE_DIFF_FLOOR", "LOOP_DETECTED"}

    observations: list[str] = []

    if odr_stop_reason in {"FORMAT_VIOLATION", "CODE_LEAK", "SHAPE_VIOLATION"}:
        observations.append(
            f"ODR terminated early with {odr_stop_reason} — coordinated output is unreliable for this scenario."
        )
    elif not odr_converged:
        observations.append(
            f"ODR did not converge (stop_reason={odr_stop_reason}). "
            "The coordinated output may still be changing."
        )
    else:
        observations.append(
            f"ODR converged cleanly (stop_reason={odr_stop_reason}) "
            f"in {odr_state.get('history_round_count', '?')} rounds."
        )

    if single_vs_odr_diff_ratio is not None:
        if single_vs_odr_diff_ratio < 0.05:
            observations.append(
                "Single-shot and ODR outputs are nearly identical "
                f"(diff_ratio={single_vs_odr_diff_ratio:.4f}). "
                "ODR coordination added no structural change in this case."
            )
        elif single_vs_odr_diff_ratio > 0.5:
            observations.append(
                "ODR produced substantially different output from single-shot "
                f"(diff_ratio={single_vs_odr_diff_ratio:.4f}). "
                "Review whether the change represents improvement or drift."
            )
        else:
            observations.append(
                f"Moderate structural divergence between modes "
                f"(diff_ratio={single_vs_odr_diff_ratio:.4f})."
            )

    if constraint_delta > 0:
        observations.append(
            f"ODR captured {constraint_delta} more constraint verb(s) than single-shot."
        )
    elif constraint_delta < 0:
        observations.append(
            f"Single-shot captured {abs(constraint_delta)} more constraint verb(s) than ODR."
        )

    if decision_required_delta < 0:
        observations.append(
            f"ODR resolved {abs(decision_required_delta)} more open decision(s) than single-shot."
        )
    elif decision_required_delta > 0:
        observations.append(
            f"ODR left {decision_required_delta} more decision(s) unresolved than single-shot."
        )

    if single_analysis.get("is_empty") and not odr_analysis.get("is_empty"):
        observations.append(
            "Single-shot produced an effectively empty requirement; ODR recovered it."
        )
    elif odr_analysis.get("is_empty") and not single_analysis.get("is_empty"):
        observations.append(
            "WARNING: ODR produced an effectively empty final requirement despite loop iterations."
        )

    return {
        "scenario_id": scenario_id,
        "single_shot": {
            "requirement_text": single_req,
            "analysis": single_analysis,
            "latency_ms": int(single.get("latency_ms") or 0),
        },
        "coordinated": {
            "requirement_text": odr_req,
            "analysis": odr_analysis,
            "total_latency_ms": int(coordinated.get("total_latency_ms") or 0),
            "rounds_used": int(odr_state.get("history_round_count") or 0),
            "stop_reason": odr_stop_reason,
            "diff_ratio_final": odr_state.get("diff_ratio_final"),
            "converged": odr_converged,
        },
        "deltas": {
            "constraint_count_delta": constraint_delta,
            "decision_required_delta": decision_required_delta,
            "word_count_delta": word_count_delta,
        },
        "similarity": {
            "single_vs_odr_diff_ratio": single_vs_odr_diff_ratio,
            "single_vs_odr_jaccard_sim": single_vs_odr_jaccard,
        },
        "observations": observations,
    }


# ---------------------------------------------------------------------------
# Aggregate summary
# ---------------------------------------------------------------------------


def _build_aggregate_summary(comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Roll up all scenario comparisons into a single readable summary.
    This is the top-level answer to: "does ODR help for 7B models?"
    """
    total = len(comparisons)
    if total == 0:
        return {"verdict": "NO_DATA"}

    converged = sum(1 for c in comparisons if c["coordinated"]["converged"])
    odr_more_constraints = sum(1 for c in comparisons if c["deltas"]["constraint_count_delta"] > 0)
    odr_fewer_decisions = sum(1 for c in comparisons if c["deltas"]["decision_required_delta"] < 0)
    odr_early_stop = sum(
        1 for c in comparisons
        if c["coordinated"]["stop_reason"] in {"FORMAT_VIOLATION", "CODE_LEAK", "SHAPE_VIOLATION"}
    )

    diff_ratios = [
        c["similarity"]["single_vs_odr_diff_ratio"]
        for c in comparisons
        if c["similarity"]["single_vs_odr_diff_ratio"] is not None
    ]
    mean_diff_ratio = (sum(diff_ratios) / len(diff_ratios)) if diff_ratios else None

    single_latencies = [c["single_shot"]["latency_ms"] for c in comparisons]
    odr_latencies = [c["coordinated"]["total_latency_ms"] for c in comparisons]
    mean_single_latency = int(sum(single_latencies) / total) if single_latencies else 0
    mean_odr_latency = int(sum(odr_latencies) / total) if odr_latencies else 0

    mean_rounds = (
        sum(c["coordinated"]["rounds_used"] for c in comparisons) / total
    )

    # High-level verdict
    if odr_early_stop / total > 0.5:
        verdict = "FAIL_ODR_UNRELIABLE"
        headline = (
            "ODR failed to complete cleanly on more than half the scenarios. "
            "The model cannot reliably maintain the required structured format. "
            "Single-shot is the better choice until format compliance improves."
        )
    elif converged / total >= 0.6 and odr_more_constraints / total >= 0.5:
        verdict = "PASS_ODR_ADDS_VALUE"
        headline = (
            f"ODR converged on {converged}/{total} scenarios and added measurable "
            f"constraints on {odr_more_constraints}/{total}. Coordination is providing value."
        )
    elif converged / total >= 0.4:
        verdict = "PARTIAL_MIXED"
        headline = (
            f"ODR converged on {converged}/{total} scenarios. Results are mixed. "
            "Review per-scenario observations to identify where coordination helps."
        )
    else:
        verdict = "FAIL_LOW_CONVERGENCE"
        headline = (
            f"ODR converged on only {converged}/{total} scenarios. "
            "Single-shot is likely comparable or better for this model pair on these tasks."
        )

    return {
        "verdict": verdict,
        "headline": headline,
        "total_scenarios": total,
        "odr_converged": converged,
        "convergence_rate": round(converged / total, 4),
        "odr_early_stop_scenarios": odr_early_stop,
        "odr_more_constraints_scenarios": odr_more_constraints,
        "odr_fewer_decisions_scenarios": odr_fewer_decisions,
        "mean_diff_ratio_single_vs_odr": round(mean_diff_ratio, 4) if mean_diff_ratio is not None else None,
        "mean_single_latency_ms": mean_single_latency,
        "mean_odr_latency_ms": mean_odr_latency,
        "latency_overhead_ratio": (
            round(mean_odr_latency / mean_single_latency, 2)
            if mean_single_latency > 0 else None
        ),
        "mean_rounds_to_stop": round(mean_rounds, 2),
    }


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------


def _collect_ollama_version() -> str:
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True, text=True, check=False, timeout=5,
        )
        return (result.stdout or result.stderr or "").strip().splitlines()[0] if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _collect_environment(
    *, architect_model: str, auditor_model: str
) -> dict[str, Any]:
    return {
        "os": platform.system(),
        "arch": platform.machine(),
        "python_version": platform.python_version(),
        "ollama_version": _collect_ollama_version(),
        "llm_provider": str(os.getenv("ORKET_LLM_PROVIDER", "ollama")),
        "ollama_host": str(os.getenv("ORKET_LLM_OLLAMA_HOST", "http://localhost:11434")),
        "architect_model": architect_model,
        "auditor_model": auditor_model,
    }


# ---------------------------------------------------------------------------
# Per-pair runner
# ---------------------------------------------------------------------------


async def _run_pair(
    *,
    architect_model: str,
    auditor_model: str,
    scenario_inputs: list[dict[str, Any]],
    rounds: int,
    odr_cfg: ReactorConfig,
    temperature: float,
    timeout: int,
) -> dict[str, Any]:
    scenario_results: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []

    started = datetime.now(UTC).isoformat()

    for scenario_input in scenario_inputs:
        scenario_id = str(scenario_input.get("id") or "?")
        print(f"    scenario={scenario_id}", flush=True)

        # --- Single-shot ---
        print(f"      [single-shot] ...", flush=True)
        try:
            single_result = await _run_single_shot(
                scenario_input=scenario_input,
                architect_model=architect_model,
                temperature=temperature,
                timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"      [single-shot] ERROR: {exc}", flush=True)
            single_result = {
                "mode": "single_shot",
                "scenario_id": scenario_id,
                "raw_output": "",
                "requirement_text": "",
                "analysis": _analyze_requirement(""),
                "latency_ms": 0,
                "runner_error": str(exc),
            }

        single_req = str(single_result.get("requirement_text") or "")
        print(
            f"      [single-shot] done  "
            f"words={single_result['analysis']['word_count']}  "
            f"constraints={single_result['analysis']['constraint_count']}  "
            f"latency={single_result.get('latency_ms', 0)}ms",
            flush=True,
        )

        # --- Coordinated (ODR) ---
        print(f"      [coordinated] ...", flush=True)
        try:
            odr_result = await _run_coordinated(
                scenario_input=scenario_input,
                architect_model=architect_model,
                auditor_model=auditor_model,
                rounds=rounds,
                odr_cfg=odr_cfg,
                temperature=temperature,
                timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"      [coordinated] ERROR: {exc}", flush=True)
            odr_result = {
                "mode": "coordinated",
                "scenario_id": scenario_id,
                "rounds": [],
                "final_requirement_text": "",
                "analysis": _analyze_requirement(""),
                "total_latency_ms": 0,
                "odr_final_state": {
                    "history_v": [],
                    "history_round_count": 0,
                    "stable_count": 0,
                    "stop_reason": f"RUNNER_ERROR:{type(exc).__name__}",
                    "diff_ratio_final": None,
                },
                "runner_error": str(exc),
            }

        odr_state = odr_result.get("odr_final_state") or {}
        print(
            f"      [coordinated] done  "
            f"stop_reason={odr_state.get('stop_reason', '?')}  "
            f"rounds={odr_state.get('history_round_count', '?')}  "
            f"words={odr_result['analysis']['word_count']}  "
            f"constraints={odr_result['analysis']['constraint_count']}  "
            f"latency={odr_result.get('total_latency_ms', 0)}ms",
            flush=True,
        )

        # --- Comparison ---
        comparison = _build_comparison(
            scenario_id=scenario_id,
            single=single_result,
            coordinated=odr_result,
        )
        for obs in comparison["observations"]:
            print(f"      -> {obs}", flush=True)

        scenario_results.append(
            {
                "scenario_id": scenario_id,
                "single_shot": single_result,
                "coordinated": odr_result,
            }
        )
        comparisons.append(comparison)

    ended = datetime.now(UTC).isoformat()
    aggregate = _build_aggregate_summary(comparisons)

    return {
        "architect_model": architect_model,
        "auditor_model": auditor_model,
        "started_at": started,
        "ended_at": ended,
        "scenarios": scenario_results,
        "comparisons": comparisons,
        "aggregate_summary": aggregate,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_list(raw: str) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


async def _main_async(args: argparse.Namespace) -> int:
    architect_models = _parse_list(args.architect_model)
    auditor_models = _parse_list(args.auditor_model)

    if not architect_models:
        print("ERROR: --architect-model is required.", file=sys.stderr)
        return 1
    if not auditor_models:
        print("ERROR: --auditor-model is required.", file=sys.stderr)
        return 1

    scenarios = _load_scenarios()
    selected_ids = set(_parse_list(args.scenario_ids))
    if selected_ids:
        scenarios = [s for s in scenarios if str(s.get("id")) in selected_ids]
    if args.max_scenarios > 0:
        scenarios = scenarios[: args.max_scenarios]

    if not scenarios:
        print("ERROR: No scenarios loaded.", file=sys.stderr)
        return 1

    scenario_inputs = [_load_scenario_inputs(s) for s in scenarios]

    odr_cfg = ReactorConfig(
        max_rounds=args.max_rounds,
        diff_floor_pct=args.diff_floor_pct,
        stable_rounds=args.stable_rounds,
        shingle_k=3,
        margin=0.02,
        min_loop_sim=0.65,
        code_leak_patterns=list(DEFAULT_CODE_LEAK_PATTERNS),
        leak_gate_mode=str(args.leak_gate_mode or "balanced_v1"),
    )

    print("[COMPARE] Single-shot vs ODR-coordinated comparison", flush=True)
    print(f"  architect_models={architect_models}", flush=True)
    print(f"  auditor_models={auditor_models}", flush=True)
    print(f"  scenarios={[s['id'] for s in scenarios]}", flush=True)
    print(f"  rounds={args.rounds}  max_rounds={args.max_rounds}", flush=True)
    print(f"  temperature={args.temperature}  timeout={args.timeout}s", flush=True)
    print()

    wall_start = time.perf_counter()
    run_started = datetime.now(UTC).isoformat()

    all_pair_results: list[dict[str, Any]] = []

    for architect_model in architect_models:
        for auditor_model in auditor_models:
            print(
                f"[PAIR] architect={architect_model}  auditor={auditor_model}",
                flush=True,
            )
            pair_result = await _run_pair(
                architect_model=architect_model,
                auditor_model=auditor_model,
                scenario_inputs=scenario_inputs,
                rounds=args.rounds,
                odr_cfg=odr_cfg,
                temperature=args.temperature,
                timeout=args.timeout,
            )
            all_pair_results.append(pair_result)

            agg = pair_result["aggregate_summary"]
            print(f"\n  [PAIR SUMMARY] verdict={agg['verdict']}", flush=True)
            print(f"  {agg['headline']}", flush=True)
            print(
                f"  convergence_rate={agg['convergence_rate']}  "
                f"mean_rounds={agg['mean_rounds_to_stop']}  "
                f"latency_overhead={agg.get('latency_overhead_ratio', 'n/a')}x",
                flush=True,
            )
            print()

    run_ended = datetime.now(UTC).isoformat()
    duration_ms = int((time.perf_counter() - wall_start) * 1000)

    # Collect environment from first pair result config
    environment = _collect_environment(
        architect_model=architect_models[0],
        auditor_model=auditor_models[0],
    )

    payload = {
        "run_v": "single_vs_coordinated.v1",
        "generated_at": run_started,
        "ended_at": run_ended,
        "duration_ms": duration_ms,
        "config": {
            "architect_models": architect_models,
            "auditor_models": auditor_models,
            "scenario_ids": [s.get("id") for s in scenarios],
            "rounds": args.rounds,
            "max_rounds": args.max_rounds,
            "odr_config": odr_cfg.as_dict(),
            "temperature": args.temperature,
            "timeout": args.timeout,
        },
        "environment": environment,
        "pairs": all_pair_results,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(_json_safe(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"[COMPARE] Wrote {out_path}", flush=True)

    # Final cross-pair summary to stdout
    print("\n--- Cross-Pair Verdict Summary ---", flush=True)
    for pair in all_pair_results:
        agg = pair["aggregate_summary"]
        print(
            f"  {pair['architect_model']} / {pair['auditor_model']}"
            f"  verdict={agg['verdict']}"
            f"  converged={agg['odr_converged']}/{agg['total_scenarios']}"
            f"  overhead={agg.get('latency_overhead_ratio', 'n/a')}x",
            flush=True,
        )

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare single-shot vs ODR-coordinated model output.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--architect-model",
        default=DEFAULT_ARCHITECT,
        help="Comma-separated architect model ID(s).",
    )
    parser.add_argument(
        "--auditor-model",
        default=DEFAULT_AUDITOR,
        help="Comma-separated auditor model ID(s).",
    )
    parser.add_argument(
        "--scenario-ids",
        default="",
        help="Comma-separated scenario IDs. Empty = all.",
    )
    parser.add_argument("--max-scenarios", type=int, default=0, help="Limit scenarios (0 = all).")
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    parser.add_argument("--max-rounds", type=int, default=DEFAULT_ROUNDS)
    parser.add_argument("--diff-floor-pct", type=float, default=0.05)
    parser.add_argument("--stable-rounds", type=int, default=2)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--leak-gate-mode",
        choices=["strict", "balanced_v1"],
        default="balanced_v1",
    )
    parser.add_argument(
        "--out",
        default="benchmarks/results/odr/single_vs_coordinated.json",
        help="Output JSON path.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
