from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from orket.adapters.llm.local_model_provider import LocalModelProvider
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger
    from orket.adapters.llm.local_model_provider import LocalModelProvider


DEFAULT_SCORE_REPORT = Path("benchmarks/staging/General/prompt_reforger_gemma_tool_use_score.json")
DEFAULT_INVENTORY = Path("benchmarks/staging/General/prompt_reforger_gemma_tool_use_inventory.json")
DEFAULT_OUTPUT = Path("benchmarks/staging/General/prompt_reforger_gemma_tool_use_judge.json")
IMPLEMENTATION_PLAN_REF = "docs/projects/PromptReforgerToolCompatibility/PROMPT_REFORGER_GEMMA_TOOL_USE_IMPLEMENTATION_PLAN.md"
JUDGE_PROTOCOL_REF = "docs/projects/PromptReforgerToolCompatibility/FUNCTIONGEMMA_TOOL_CALL_JUDGE_PROTOCOL.md"

_DIMENSIONS = (
    "tool_selection",
    "argument_presence",
    "argument_shape",
    "extra_undeclared_tool_calls",
    "malformed_output_shape",
)
_VERDICTS = {"pass", "fail", "inconclusive"}
_JUDGE_TOOL_NAME = "emit_judgment"


@dataclass(frozen=True)
class JudgeTarget:
    inventory_role: str
    provider: str
    model: str
    base_url: str
    quantization: str
    observed_path: str
    alias_resolution: str
    model_identity: str


def _now_utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _resolve_repo_path(repo_root: Path, raw_path: str) -> Path:
    candidate = Path(str(raw_path))
    if candidate.is_absolute():
        return candidate
    return repo_root / candidate


def _relativize(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the bounded advisory FunctionGemma judge over one frozen Gemma tool-use score report."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--score-report", default=str(DEFAULT_SCORE_REPORT))
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--timeout-sec", type=int, default=60)
    return parser


def _extract_json_object(blob: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    text = str(blob or "").strip()
    if not text:
        return None
    if "```" in text:
        chunks = text.split("```")
        for chunk in chunks:
            candidate = chunk.strip()
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    start = 0
    while True:
        brace_index = text.find("{", start)
        if brace_index < 0:
            return None
        try:
            parsed, end = decoder.raw_decode(text[brace_index:])
        except json.JSONDecodeError:
            start = brace_index + 1
            continue
        if isinstance(parsed, dict):
            return parsed
        start = brace_index + max(end, 1)


def _resolve_judge_targets(inventory: dict[str, Any]) -> tuple[list[JudgeTarget], str | None]:
    summary = inventory.get("summary") if isinstance(inventory.get("summary"), dict) else {}
    inventory_rows = inventory.get("inventory_targets") if isinstance(inventory.get("inventory_targets"), list) else []
    available_targets: list[JudgeTarget] = []
    for wanted_role, observed_path in (("judge_primary", "primary"), ("judge_fallback", "fallback")):
        row = next(
            (
                item
                for item in inventory_rows
                if isinstance(item, dict) and str(item.get("role") or "").strip() == wanted_role
            ),
            None,
        )
        if row is None:
            continue
        runtime_target = row.get("runtime_target") if isinstance(row.get("runtime_target"), dict) else {}
        if str(runtime_target.get("status") or "").strip().upper() != "OK":
            continue
        available_targets.append(
            JudgeTarget(
                inventory_role=wanted_role,
                provider=str(row.get("requested_provider") or "").strip(),
                model=str(runtime_target.get("requested_model") or row.get("requested_model") or "").strip(),
                base_url=str(runtime_target.get("base_url") or "").strip(),
                quantization=str(row.get("preferred_quantization") or "Q8_0").strip(),
                observed_path=observed_path,
                alias_resolution=str(row.get("alias_resolution") or "canonical").strip(),
                model_identity=str(row.get("model_identity") or "").strip(),
            )
        )
    if available_targets:
        return available_targets, None
    if str(summary.get("judge_path") or "blocked").strip().lower() not in {"primary", "fallback"}:
        return [], "inventory_judge_path_blocked"
    return [], "no_admitted_judge_path_available"


def _parser_dimensions(turn: dict[str, Any], diagnostics: list[dict[str, Any]]) -> dict[str, str]:
    accepted = turn.get("accepted_tool_calls") if isinstance(turn.get("accepted_tool_calls"), list) else []
    rejected = turn.get("rejected_tool_calls") if isinstance(turn.get("rejected_tool_calls"), list) else []
    defects = turn.get("argument_shape_defects") if isinstance(turn.get("argument_shape_defects"), list) else []
    required_tools = {
        str(token).strip()
        for token in (turn.get("required_action_tools") or [])
        if str(token).strip()
    }
    accepted_tools = {
        str((call.get("tool") if isinstance(call, dict) else "") or "").strip()
        for call in accepted
        if isinstance(call, dict)
    }
    malformed = not (
        accepted
        or any(str(row.get("stage") or "").strip() == "native_tool_calls_success" for row in diagnostics if isinstance(row, dict))
    )
    missing_argument = any(
        str(row.get("reason") or "").strip().startswith("missing_")
        for row in defects
        if isinstance(row, dict)
    )
    return {
        "tool_selection": "pass" if required_tools.issubset(accepted_tools) else "fail",
        "argument_presence": "fail" if missing_argument else "pass",
        "argument_shape": "fail" if defects else "pass",
        "extra_undeclared_tool_calls": (
            "fail"
            if any(
                str(row.get("reason") or "").strip() == "undeclared_tool"
                and str(row.get("tool") or "").strip() not in accepted_tools
                for row in rejected
                if isinstance(row, dict)
            )
            else "pass"
        ),
        "malformed_output_shape": "fail" if malformed else "pass",
    }


def _parser_overall(turn: dict[str, Any], diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    dimensions = _parser_dimensions(turn, diagnostics)
    verdict = "pass"
    if not bool(turn.get("valid_completion")) or any(value == "fail" for value in dimensions.values()):
        verdict = "fail"
    return {"verdict": verdict, "dimensions": dimensions}


def _judge_prompt(packet: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are an advisory tool-call judge. "
                "You are not being asked to perform the listed tools. "
                f"Call {_JUDGE_TOOL_NAME} exactly once with one bounded advisory judgment. "
                "verdict and every dimension must be pass, fail, or inconclusive. "
                "Do not refuse, do not explain capabilities, and do not answer in prose."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "slice_id": packet["slice_id"],
                    "role_name": packet["role_name"],
                    "required_action_tools": packet["required_action_tools"],
                    "required_read_paths": packet["required_read_paths"],
                    "required_write_paths": packet["required_write_paths"],
                    "required_statuses": packet["required_statuses"],
                    "provider_tool_calls": packet["provider_tool_calls"],
                    "parsed_tool_calls": packet["parsed_tool_calls"],
                    "argument_shape_defects": packet["argument_shape_defects"],
                    "valid_completion": packet["valid_completion"],
                },
                indent=2,
                ensure_ascii=False,
            ),
        },
    ]


def _judge_native_tools() -> list[dict[str, Any]]:
    properties = {
        "verdict": {
            "type": "string",
            "enum": sorted(_VERDICTS),
            "description": "Overall advisory verdict for the observed turn.",
        },
        "tool_selection": {
            "type": "string",
            "enum": sorted(_VERDICTS),
            "description": "Whether the observed tool selection satisfied the required action tools.",
        },
        "argument_presence": {
            "type": "string",
            "enum": sorted(_VERDICTS),
            "description": "Whether required arguments were present.",
        },
        "argument_shape": {
            "type": "string",
            "enum": sorted(_VERDICTS),
            "description": "Whether the observed arguments matched the admitted shape.",
        },
        "extra_undeclared_tool_calls": {
            "type": "string",
            "enum": sorted(_VERDICTS),
            "description": "Whether undeclared extra tool calls were observed.",
        },
        "malformed_output_shape": {
            "type": "string",
            "enum": sorted(_VERDICTS),
            "description": "Whether the provider output shape was malformed for the bounded turn contract.",
        },
        "rationale": {
            "type": "string",
            "description": "Short evidence-based reason for the advisory judgment.",
        },
    }
    return [
        {
            "type": "function",
            "function": {
                "name": _JUDGE_TOOL_NAME,
                "description": "Emit exactly one advisory judgment for the supplied evidence packet.",
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": list(properties.keys()),
                    "additionalProperties": False,
                },
            },
        }
    ]


def _turn_packets(score_report: dict[str, Any], repo_root: Path) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    for slice_result in score_report.get("slice_results") or []:
        if not isinstance(slice_result, dict):
            continue
        for turn in slice_result.get("evaluated_turns") or []:
            if not isinstance(turn, dict):
                continue
            diagnostics_ref = _resolve_repo_path(repo_root, str(turn.get("tool_parser_diagnostics_ref") or ""))
            messages_ref = _resolve_repo_path(repo_root, str(turn.get("messages_ref") or ""))
            response_raw_ref = _resolve_repo_path(repo_root, str(turn.get("model_response_raw_ref") or ""))
            parsed_ref = _resolve_repo_path(repo_root, str(turn.get("parsed_tool_calls_ref") or ""))
            diagnostics = _read_json(diagnostics_ref) if diagnostics_ref.exists() else []
            messages = _read_json(messages_ref) if messages_ref.exists() else []
            response_raw = _read_json(response_raw_ref) if response_raw_ref.exists() else {}
            parsed_tool_calls = _read_json(parsed_ref) if parsed_ref.exists() else []
            packets.append(
                {
                    "slice_id": str(slice_result.get("slice_id") or "").strip(),
                    "issue_id": str(slice_result.get("issue_id") or "").strip(),
                    "role_name": str(slice_result.get("role_name") or "").strip(),
                    "description": str(slice_result.get("description") or "").strip(),
                    "turn_dir": str(turn.get("turn_dir") or "").strip(),
                    "turn_index": int(turn.get("turn_index") or 0),
                    "required_action_tools": list(slice_result.get("required_action_tools") or []),
                    "required_read_paths": list(slice_result.get("required_read_paths") or []),
                    "required_write_paths": list(slice_result.get("required_write_paths") or []),
                    "required_statuses": list(slice_result.get("required_statuses") or []),
                    "accepted_tool_calls": list(turn.get("accepted_tool_calls") or []),
                    "rejected_tool_calls": list(turn.get("rejected_tool_calls") or []),
                    "argument_shape_defects": list(turn.get("argument_shape_defects") or []),
                    "valid_completion": bool(turn.get("valid_completion", False)),
                    "diagnostics": diagnostics if isinstance(diagnostics, list) else [],
                    "messages": messages if isinstance(messages, list) else [],
                    "model_response_raw": response_raw if isinstance(response_raw, dict) else {},
                    "parsed_tool_calls": parsed_tool_calls if isinstance(parsed_tool_calls, list) else [],
                    "messages_ref": str(turn.get("messages_ref") or ""),
                    "model_response_raw_ref": str(turn.get("model_response_raw_ref") or ""),
                    "parsed_tool_calls_ref": str(turn.get("parsed_tool_calls_ref") or ""),
                }
            )
    return packets


def _payload_signal_score(payload: dict[str, Any]) -> int:
    score = 0
    verdict = str(payload.get("verdict") or "").strip().lower()
    if verdict in _VERDICTS:
        score += 2
    if isinstance(payload.get("dimensions"), dict):
        score += sum(1 for name in _DIMENSIONS if name in payload["dimensions"])
    else:
        score += sum(1 for name in _DIMENSIONS if name in payload)
    if any(key in payload for key in ("rationale", "Rationale", "notes")):
        score += 1
    return score


def _extract_native_tool_payload(raw_payload: dict[str, Any]) -> tuple[dict[str, Any] | None, int]:
    tool_calls = raw_payload.get("tool_calls") if isinstance(raw_payload.get("tool_calls"), list) else []
    parsed_candidates: list[dict[str, Any]] = []
    for item in tool_calls:
        if not isinstance(item, dict):
            continue
        function_payload = item.get("function") if isinstance(item.get("function"), dict) else {}
        if str(function_payload.get("name") or "").strip() != _JUDGE_TOOL_NAME:
            continue
        arguments = function_payload.get("arguments")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                continue
        if isinstance(arguments, dict):
            parsed_candidates.append(arguments)
    if not parsed_candidates:
        return None, len(tool_calls)
    best_payload = max(parsed_candidates, key=_payload_signal_score)
    return best_payload, len(tool_calls)


def _normalize_dimension_value(name: str, raw_value: Any) -> str:
    token = str(raw_value or "").strip().lower()
    if token in _VERDICTS:
        return token
    if name == "extra_undeclared_tool_calls" and isinstance(raw_value, list):
        return "pass" if not raw_value else "fail"
    if isinstance(raw_value, bool):
        return "fail" if raw_value else "pass"
    return "inconclusive"


def _normalize_judge_payload(payload: dict[str, Any]) -> dict[str, Any]:
    verdict = str(payload.get("verdict") or "").strip().lower()
    if verdict not in _VERDICTS:
        verdict = "inconclusive"
    dimensions_raw = payload.get("dimensions") if isinstance(payload.get("dimensions"), dict) else {}
    dimensions = {
        name: _normalize_dimension_value(name, dimensions_raw.get(name, payload.get(name)))
        for name in _DIMENSIONS
    }
    return {
        "verdict": verdict,
        "dimensions": dimensions,
        "rationale": str(payload.get("rationale") or payload.get("Rationale") or payload.get("notes") or "").strip(),
    }


def _judgment_summary(turn_judgments: list[dict[str, Any]]) -> dict[str, int]:
    agreement_count = sum(1 for row in turn_judgments if bool(row.get("judge_vs_parser_agreement")))
    inconclusive_count = sum(
        1 for row in turn_judgments if str((row.get("judge_advisory_verdict") or {}).get("verdict") or "") == "inconclusive"
    )
    return {
        "turns_total": len(turn_judgments),
        "agreement_count": agreement_count,
        "disagreement_count": len(turn_judgments) - agreement_count,
        "inconclusive_count": inconclusive_count,
    }


async def _run_judgments(
    *,
    target: JudgeTarget,
    packets: list[dict[str, Any]],
    timeout_sec: int,
) -> list[dict[str, Any]]:
    provider = LocalModelProvider(
        model=target.model,
        timeout=max(1, int(timeout_sec)),
        provider=target.provider,
        base_url=target.base_url,
    )
    results: list[dict[str, Any]] = []
    try:
        for packet in packets:
            parser_truth = _parser_overall(packet, packet["diagnostics"])
            evidence_packet = {
                "judge_protocol_ref": JUDGE_PROTOCOL_REF,
                "slice_id": packet["slice_id"],
                "issue_id": packet["issue_id"],
                "role_name": packet["role_name"],
                "turn_index": packet["turn_index"],
                "turn_dir": packet["turn_dir"],
                "description": packet["description"],
                "required_action_tools": packet["required_action_tools"],
                "required_read_paths": packet["required_read_paths"],
                "required_write_paths": packet["required_write_paths"],
                "required_statuses": packet["required_statuses"],
                "prompt_messages": packet["messages"],
                "provider_tool_calls": list(packet["model_response_raw"].get("tool_calls") or []),
                "parsed_tool_calls": packet["parsed_tool_calls"],
                "accepted_tool_calls": packet["accepted_tool_calls"],
                "rejected_tool_calls": packet["rejected_tool_calls"],
                "argument_shape_defects": packet["argument_shape_defects"],
                "tool_parser_diagnostics": packet["diagnostics"],
                "valid_completion": packet["valid_completion"],
                "parser_authority_truth": parser_truth,
            }
            try:
                response = await provider.complete(
                    _judge_prompt(evidence_packet),
                    runtime_context={
                        "local_prompt_task_class": "strict_json",
                        "protocol_governed_enabled": True,
                        "native_tools": _judge_native_tools(),
                        "native_tool_choice": "required",
                        "native_payload_overrides": {"reasoning_effort": "none"},
                    },
                )
                response_content = str(getattr(response, "content", "") or "")
                response_raw = dict(getattr(response, "raw", {}) or {})
                tool_payload, tool_call_count = _extract_native_tool_payload(response_raw)
                response_raw["judge_tool_call_count"] = int(tool_call_count)
                parsed_judgment = _normalize_judge_payload(tool_payload or _extract_json_object(response_content) or {})
            except Exception as exc:  # pragma: no cover - live-path failure recording
                response_content = ""
                response_raw = {"error": str(exc)}
                parsed_judgment = {
                    "verdict": "inconclusive",
                    "dimensions": {name: "inconclusive" for name in _DIMENSIONS},
                    "rationale": str(exc),
                }
            results.append(
                {
                    "slice_id": packet["slice_id"],
                    "issue_id": packet["issue_id"],
                    "role_name": packet["role_name"],
                    "turn_index": packet["turn_index"],
                    "turn_dir": packet["turn_dir"],
                    "parser_authority_truth": parser_truth,
                    "judge_advisory_verdict": parsed_judgment,
                    "judge_vs_parser_agreement": parsed_judgment["verdict"] == parser_truth["verdict"],
                    "messages_ref": packet["messages_ref"],
                    "model_response_raw_ref": packet["model_response_raw_ref"],
                    "parsed_tool_calls_ref": packet["parsed_tool_calls_ref"],
                    "evidence_packet": evidence_packet,
                    "judge_response": {
                        "content": response_content,
                        "raw": response_raw,
                    },
                }
            )
    finally:
        await provider.close()
    return results


def run_judge(*, repo_root: Path, score_report: dict[str, Any], inventory: dict[str, Any], timeout_sec: int) -> dict[str, Any]:
    targets, blocker = _resolve_judge_targets(inventory)
    if not targets:
        return {
            "schema_version": "prompt_reforger_functiongemma_judge.v1",
            "generated_at_utc": _now_utc_iso(),
            "proof_type": "live",
            "observed_path": "blocked",
            "observed_result": "environment blocker",
            "implementation_plan_ref": IMPLEMENTATION_PLAN_REF,
            "judge_protocol_ref": JUDGE_PROTOCOL_REF,
            "blocking_error": blocker or "judge_target_unresolved",
            "score_report_ref": "",
            "judge_target": {},
            "turn_judgments": [],
            "summary": {"turns_total": 0, "agreement_count": 0, "disagreement_count": 0, "inconclusive_count": 0},
        }
    packets = _turn_packets(score_report, repo_root)
    selected_target: JudgeTarget | None = None
    turn_judgments: list[dict[str, Any]] = []
    summary: dict[str, int] = {"turns_total": 0, "agreement_count": 0, "disagreement_count": 0, "inconclusive_count": 0}
    attempted_targets: list[dict[str, Any]] = []
    for target in targets:
        candidate_turn_judgments = asyncio.run(_run_judgments(target=target, packets=packets, timeout_sec=timeout_sec))
        candidate_summary = _judgment_summary(candidate_turn_judgments)
        attempted_targets.append(
            {
                "inventory_role": target.inventory_role,
                "provider": target.provider,
                "model": target.model,
                "observed_path": target.observed_path,
                "summary": candidate_summary,
            }
        )
        selected_target = target
        turn_judgments = candidate_turn_judgments
        summary = candidate_summary
        if candidate_summary["turns_total"] > 0 and candidate_summary["inconclusive_count"] < candidate_summary["turns_total"]:
            break
    if selected_target is None:
        raise RuntimeError("judge target resolution produced no selected target")
    return {
        "schema_version": "prompt_reforger_functiongemma_judge.v1",
        "generated_at_utc": _now_utc_iso(),
        "proof_type": "live",
        "observed_path": selected_target.observed_path,
        "observed_result": "success" if turn_judgments and summary["inconclusive_count"] == 0 else "partial success",
        "implementation_plan_ref": IMPLEMENTATION_PLAN_REF,
        "judge_protocol_ref": JUDGE_PROTOCOL_REF,
        "blocking_error": "",
        "score_report_ref": "",
        "attempted_judge_targets": attempted_targets,
        "judge_target": {
            "inventory_role": selected_target.inventory_role,
            "provider": selected_target.provider,
            "model": selected_target.model,
            "base_url": selected_target.base_url,
            "quantization": selected_target.quantization,
            "observed_path": selected_target.observed_path,
            "alias_resolution": selected_target.alias_resolution,
            "model_identity": selected_target.model_identity,
        },
        "turn_judgments": turn_judgments,
        "summary": summary,
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = Path(str(args.repo_root)).resolve()
    score_report_path = _resolve_repo_path(repo_root, str(args.score_report))
    inventory_path = _resolve_repo_path(repo_root, str(args.inventory))
    out_path = _resolve_repo_path(repo_root, str(args.out))
    score_report = _read_json(score_report_path)
    inventory = _read_json(inventory_path)
    if not isinstance(score_report, dict):
        raise ValueError("score report must be a JSON object")
    if not isinstance(inventory, dict):
        raise ValueError("inventory must be a JSON object")
    payload = run_judge(
        repo_root=repo_root,
        score_report=score_report,
        inventory=inventory,
        timeout_sec=int(args.timeout_sec),
    )
    payload["score_report_ref"] = _relativize(score_report_path, repo_root)
    write_payload_with_diff_ledger(out_path, payload)
    print(
        json.dumps(
            {
                "observed_path": str(payload.get("observed_path") or ""),
                "observed_result": str(payload.get("observed_result") or ""),
                "turns_total": int((payload.get("summary") or {}).get("turns_total") or 0),
                "out": _relativize(out_path, repo_root),
            }
        )
    )
    return 0 if str(payload.get("observed_path") or "") != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
