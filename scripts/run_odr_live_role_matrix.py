from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import sys
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.adapters.llm.local_model_provider import LocalModelProvider  # noqa: E402
from orket.kernel.v1.odr.core import ReactorConfig, ReactorState, run_round  # noqa: E402


DEFAULT_ARCHITECTS = [
    "Command-R:35B",
    "qwen2.5:14b",
    "llama3.1:8b",
]

DEFAULT_AUDITORS = [
    "deepseek-r1:32b",
    "gemma3:27b",
]

SCENARIO_ROOT = Path("tests/kernel/v1/vectors/odr/refinement")


@dataclass(frozen=True)
class Pairing:
    architect: str
    auditor: str


def _parse_list(raw: str) -> List[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    return str(value)


def _load_scenarios() -> List[Dict[str, Any]]:
    path = SCENARIO_ROOT / "scenarios.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_scenario_inputs(scenario: Dict[str, Any]) -> Dict[str, Any]:
    folder = SCENARIO_ROOT / str(scenario["path"])
    seed_file = str(scenario.get("seed_file") or "").strip()
    payload: Dict[str, Any] = {
        "id": scenario["id"],
        "path": scenario["path"],
        "R0": (folder / "R0.md").read_text(encoding="utf-8"),
        "A0": json.loads((folder / "A0.json").read_text(encoding="utf-8")),
    }
    if seed_file:
        payload["seed"] = json.loads((folder / seed_file).read_text(encoding="utf-8"))
    else:
        payload["seed"] = {}
    return payload


def _scenario_brief(scenario_input: Dict[str, Any]) -> str:
    issue_lines = []
    for issue in scenario_input.get("A0", []):
        issue_lines.append(
            f"- id={issue.get('id')} status={issue.get('status')} required_action={issue.get('required_action')}"
        )
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
    scenario_input: Dict[str, Any],
    current_requirement: str,
    prior_auditor_output: str,
    round_index: int,
) -> List[Dict[str, str]]:
    system = (
        "You are the Architect role for requirement refinement.\n"
        "Return exactly these sections, once each, in this exact order:\n"
        "### REQUIREMENT\n"
        "### CHANGELOG\n"
        "### ASSUMPTIONS\n"
        "### OPEN_QUESTIONS\n"
        "Rules:\n"
        "- No code fences.\n"
        "- No source code.\n"
        "- Keep statements concrete and testable.\n"
        "- Preserve prior accepted constraints unless explicitly replaced.\n"
        "- If a required numeric value is missing from seed input, do not invent it; use DECISION_REQUIRED wording.\n"
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
    scenario_input: Dict[str, Any],
    architect_output: str,
    round_index: int,
) -> List[Dict[str, str]]:
    system = (
        "You are the Auditor role for requirement refinement.\n"
        "Return exactly these sections, once each, in this exact order:\n"
        "### CRITIQUE\n"
        "### PATCHES\n"
        "### EDGE_CASES\n"
        "### TEST_GAPS\n"
        "Rules:\n"
        "- No code fences.\n"
        "- No source code.\n"
        "- Be adversarial and concrete.\n"
        "- Flag regressions, missing constraints, and hallucinated constants.\n"
    )
    user = (
        f"{_scenario_brief(scenario_input)}\n"
        f"Round: {round_index}\n"
        "Architect output to audit:\n"
        f"{architect_output}\n"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


async def _run_scenario_live(
    *,
    scenario_input: Dict[str, Any],
    architect_provider: LocalModelProvider,
    auditor_provider: LocalModelProvider,
    rounds: int,
    odr_cfg: ReactorConfig,
) -> Dict[str, Any]:
    state = ReactorState()
    current_requirement = str(scenario_input.get("R0") or "")
    prior_auditor_output = ""
    round_rows: List[Dict[str, Any]] = []

    for round_index in range(1, rounds + 1):
        architect_messages = _architect_messages(
            scenario_input=scenario_input,
            current_requirement=current_requirement,
            prior_auditor_output=prior_auditor_output,
            round_index=round_index,
        )
        architect_resp = await architect_provider.complete(architect_messages)
        architect_raw = str(architect_resp.content or "").strip()

        auditor_messages = _auditor_messages(
            scenario_input=scenario_input,
            architect_output=architect_raw,
            round_index=round_index,
        )
        auditor_resp = await auditor_provider.complete(auditor_messages)
        auditor_raw = str(auditor_resp.content or "").strip()

        pre_round_count = len(state.history_rounds)
        state = run_round(state, architect_raw, auditor_raw, odr_cfg)
        trace_record = state.history_rounds[-1] if len(state.history_rounds) > pre_round_count else None

        if trace_record is not None and isinstance(trace_record.get("architect_parsed"), dict):
            current_requirement = str(trace_record["architect_parsed"].get("requirement") or current_requirement)
        prior_auditor_output = auditor_raw

        round_rows.append(
            {
                "round": round_index,
                "architect_messages": architect_messages,
                "auditor_messages": auditor_messages,
                "architect_raw": architect_raw,
                "auditor_raw": auditor_raw,
                "architect_provider_raw": _json_safe(architect_resp.raw),
                "auditor_provider_raw": _json_safe(auditor_resp.raw),
                "odr_trace_record": _json_safe(trace_record),
                "state_stop_reason_after_round": state.stop_reason,
            }
        )
        if state.stop_reason is not None:
            break

    return {
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


async def _run_pairing(
    *,
    pairing: Pairing,
    scenario_inputs: List[Dict[str, Any]],
    rounds: int,
    odr_cfg: ReactorConfig,
    temperature: float,
    timeout: int,
) -> Dict[str, Any]:
    architect_provider = LocalModelProvider(
        model=pairing.architect,
        temperature=temperature,
        timeout=timeout,
    )
    auditor_provider = LocalModelProvider(
        model=pairing.auditor,
        temperature=temperature,
        timeout=timeout,
    )

    scenarios: List[Dict[str, Any]] = []
    started = datetime.now(UTC).isoformat()
    for scenario_input in scenario_inputs:
        case = await _run_scenario_live(
            scenario_input=scenario_input,
            architect_provider=architect_provider,
            auditor_provider=auditor_provider,
            rounds=rounds,
            odr_cfg=odr_cfg,
        )
        scenarios.append(case)
    ended = datetime.now(UTC).isoformat()
    return {
        "architect_model": pairing.architect,
        "auditor_model": pairing.auditor,
        "started_at": started,
        "ended_at": ended,
        "scenarios": scenarios,
    }


async def _main_async(args: argparse.Namespace) -> int:
    architects = _parse_list(args.architect_models)
    auditors = _parse_list(args.auditor_models)
    scenarios = _load_scenarios()
    selected_ids = set(_parse_list(args.scenario_ids))
    if selected_ids:
        scenarios = [row for row in scenarios if str(row.get("id")) in selected_ids]
    if args.max_scenarios > 0:
        scenarios = scenarios[: args.max_scenarios]
    scenario_inputs = [_load_scenario_inputs(row) for row in scenarios]

    pairings = [Pairing(a, b) for a, b in itertools.product(architects, auditors)]
    code_leak_patterns = None
    raw_patterns = str(args.code_leak_patterns_json or "").strip()
    if raw_patterns:
        parsed = json.loads(raw_patterns)
        if isinstance(parsed, list):
            code_leak_patterns = [str(item) for item in parsed]

    odr_cfg = ReactorConfig(
        max_rounds=args.max_rounds,
        diff_floor_pct=args.diff_floor_pct,
        stable_rounds=args.stable_rounds,
        shingle_k=args.shingle_k,
        margin=args.margin,
        min_loop_sim=args.min_loop_sim,
        code_leak_patterns=code_leak_patterns,
    )

    results: List[Dict[str, Any]] = []
    for index, pairing in enumerate(pairings, start=1):
        print(f"[{index}/{len(pairings)}] architect={pairing.architect} auditor={pairing.auditor}")
        row = await _run_pairing(
            pairing=pairing,
            scenario_inputs=scenario_inputs,
            rounds=args.rounds,
            odr_cfg=odr_cfg,
            temperature=args.temperature,
            timeout=args.timeout,
        )
        results.append(row)
        print("  -> complete")

    payload = {
        "run_v": "1.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "config": {
            "architect_models": architects,
            "auditor_models": auditors,
            "scenario_ids": [row.get("id") for row in scenarios],
            "rounds": args.rounds,
            "odr_config": odr_cfg.as_dict(),
            "temperature": args.temperature,
            "timeout": args.timeout,
        },
        "results": results,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(_json_safe(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run live model-in-loop ODR role matrix and emit round-level IO report."
    )
    parser.add_argument("--architect-models", default=",".join(DEFAULT_ARCHITECTS))
    parser.add_argument("--auditor-models", default=",".join(DEFAULT_AUDITORS))
    parser.add_argument(
        "--scenario-ids",
        default="",
        help="Comma-separated scenario ids from refinement/scenarios.json.",
    )
    parser.add_argument("--max-scenarios", type=int, default=0, help="Limit scenarios (0 means all).")
    parser.add_argument("--rounds", type=int, default=3, help="Max live LLM rounds per scenario.")
    parser.add_argument("--max-rounds", type=int, default=8)
    parser.add_argument("--diff-floor-pct", type=float, default=0.05)
    parser.add_argument("--stable-rounds", type=int, default=2)
    parser.add_argument("--shingle-k", type=int, default=3)
    parser.add_argument("--margin", type=float, default=0.02)
    parser.add_argument("--min-loop-sim", type=float, default=0.65)
    parser.add_argument(
        "--code-leak-patterns-json",
        default="",
        help="Optional JSON array override for ODR code leak regex patterns.",
    )
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--out", default="benchmarks/results/odr_live_role_matrix.json")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
