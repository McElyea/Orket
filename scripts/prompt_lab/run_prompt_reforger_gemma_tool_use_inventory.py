from __future__ import annotations

import argparse
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
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
    from scripts.providers.provider_runtime_warmup import ProviderRuntimeWarmupError, warmup_provider_model
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger
    from providers.provider_runtime_warmup import ProviderRuntimeWarmupError, warmup_provider_model


DEFAULT_OUTPUT = Path("benchmarks/staging/General/prompt_reforger_gemma_tool_use_inventory.json")
DEFAULT_TIMEOUT_S = 10.0
DEFAULT_MODEL_LOAD_TIMEOUT_S = 180.0
DEFAULT_MODEL_TTL_SEC = 600

IMPLEMENTATION_PLAN_REF = "docs/projects/PromptReforgerToolCompatibility/PROMPT_REFORGER_GEMMA_TOOL_USE_IMPLEMENTATION_PLAN.md"
BOOTSTRAP_EPIC_REF = "model/core/epics/challenge_workflow_runtime.json"
BOOTSTRAP_HARNESS_SCRIPT = "scripts/benchmarks/run_local_model_coding_challenge.py"
BOOTSTRAP_HARNESS_OUTPUT = "benchmarks/staging/General/local_model_coding_challenge_report.json"
RUNTIME_INVENTORY_SCRIPT = "scripts/prompt_lab/run_prompt_reforger_gemma_tool_use_inventory.py"

_MEASURED_OUTPUTS = (
    "accepted_tool_calls",
    "rejected_tool_calls",
    "argument_shape_defects",
    "turns_to_first_valid_tool_call",
    "turns_to_first_valid_completion",
    "final_disposition",
)


@dataclass(frozen=True)
class InventoryTarget:
    role: str
    description: str
    requested_provider: str
    requested_model: str
    provider_model_candidates: tuple[str, ...]
    model_identity: str
    model_identity_kind: str
    lane_priority: str
    preferred_quantization: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "role": self.role,
            "description": self.description,
            "requested_provider": self.requested_provider,
            "requested_model": self.requested_model,
            "provider_model_candidates": list(self.provider_model_candidates),
            "model_identity": self.model_identity,
            "model_identity_kind": self.model_identity_kind,
            "lane_priority": self.lane_priority,
        }
        if self.preferred_quantization:
            payload["preferred_quantization"] = self.preferred_quantization
        return payload


INVENTORY_TARGETS = (
    InventoryTarget(
        role="proposer_quality",
        description="Quality-oriented Gemma proposer target.",
        requested_provider="lmstudio",
        requested_model="google/gemma-3-12b-it-qat",
        provider_model_candidates=("google/gemma-3-12b-it-qat", "gemma-3-12b-it-qat"),
        model_identity="google/gemma-3-12b-it-qat",
        model_identity_kind="lmstudio_family_id",
        lane_priority="optional_quality",
    ),
    InventoryTarget(
        role="proposer_portability",
        description="Portability Gemma proposer target for smaller hardware.",
        requested_provider="lmstudio",
        requested_model="google/gemma-3-4b-it-qat",
        provider_model_candidates=("google/gemma-3-4b-it-qat", "gemma-3-4b-it-qat"),
        model_identity="google/gemma-3-4b-it-qat",
        model_identity_kind="lmstudio_family_id",
        lane_priority="required_portability",
    ),
    InventoryTarget(
        role="judge_primary",
        description="Primary FunctionGemma judge target on Ollama.",
        requested_provider="ollama",
        requested_model="functiongemma",
        provider_model_candidates=("functiongemma", "functiongemma:latest"),
        model_identity="google/functiongemma-270m-it",
        model_identity_kind="ollama_model_name",
        lane_priority="required_judge_primary",
        preferred_quantization="Q8_0",
    ),
    InventoryTarget(
        role="judge_fallback",
        description="Fallback FunctionGemma judge target on LM Studio.",
        requested_provider="lmstudio",
        requested_model="google/functiongemma-270m",
        provider_model_candidates=("google/functiongemma-270m", "functiongemma-270m-it"),
        model_identity="google/functiongemma-270m",
        model_identity_kind="lmstudio_family_id",
        lane_priority="fallback_judge",
        preferred_quantization="Q8_0",
    ),
)


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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Freeze the Prompt Reforger Gemma tool-use lane inventory and bootstrap proof-slice authority."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--timeout-sec", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--model-load-timeout-sec", type=float, default=DEFAULT_MODEL_LOAD_TIMEOUT_S)
    parser.add_argument("--model-ttl-sec", type=int, default=DEFAULT_MODEL_TTL_SEC)
    parser.add_argument(
        "--no-auto-load-local-model",
        dest="auto_load_local_model",
        action="store_false",
        help="Disable LM Studio auto-load during inventory warmup.",
    )
    parser.set_defaults(auto_load_local_model=True)
    return parser


def _judge_quant_guidance() -> dict[str, Any]:
    return {
        "canonical_underlying_model": "google/functiongemma-270m-it",
        "primary_provider_surface": {"provider": "ollama", "model": "functiongemma"},
        "primary_provider_alias_candidates": ["functiongemma:latest"],
        "fallback_provider_surface": {"provider": "lmstudio", "model": "google/functiongemma-270m"},
        "preferred_quantization": "Q8_0",
        "degradation_quantizations": ["Q4_0"],
        "notes": [
            "Q8_0 is the primary judge quant for the lane.",
            "Smaller quants remain degradation checks, not the canonical judge path.",
        ],
    }


def _bootstrap_proof_slice() -> dict[str, Any]:
    return {
        "slice_id": "challenge_workflow_runtime_bootstrap_v0",
        "status": "bootstrap_frozen",
        "epic_ref": BOOTSTRAP_EPIC_REF,
        "harness_script": BOOTSTRAP_HARNESS_SCRIPT,
        "harness_output": BOOTSTRAP_HARNESS_OUTPUT,
        "measured_outputs": list(_MEASURED_OUTPUTS),
        "notes": [
            "This bootstrap freeze binds the first tool-use slice to the existing challenge_workflow_runtime harness.",
            "It does not claim Workstream 1 is complete; the dedicated deterministic tool-use corpus still needs to be frozen separately.",
        ],
    }


def _blocking_error(
    *,
    target: InventoryTarget,
    runtime_payload: dict[str, Any],
    auto_load_local_model: bool,
) -> str | None:
    status = str(runtime_payload.get("status") or "").upper()
    if status == "OK":
        return None
    resolution_mode = str(runtime_payload.get("resolution_mode") or "").strip()
    if resolution_mode == "quarantined_provider":
        return f"Provider '{target.requested_provider}' is quarantined by policy."
    if resolution_mode == "quarantined_model":
        return (
            f"Requested model '{target.requested_model}' is quarantined for provider "
            f"'{target.requested_provider}'."
        )
    if resolution_mode == "unknown_provider_input":
        return f"Provider '{target.requested_provider}' is not admitted by the runtime target resolver."

    available_models = [str(model) for model in (runtime_payload.get("available_models") or []) if str(model).strip()]
    loaded_after = [str(model) for model in (runtime_payload.get("loaded_models_after") or []) if str(model).strip()]
    if not available_models:
        return f"No installed models were observed for provider '{target.requested_provider}'."
    if target.requested_model not in available_models:
        normalized_requested = target.requested_model.strip().lower().split("/")[-1]
        alias_candidates = sorted(
            {
                model
                for model in available_models
                if normalized_requested
                and (
                    normalized_requested == model.strip().lower().split("/")[-1]
                    or normalized_requested in model.strip().lower()
                    or model.strip().lower().split("/")[-1] in normalized_requested
                )
            }
        )
        if alias_candidates:
            return (
                f"Requested model '{target.requested_model}' was not found in installed model inventory for "
                f"provider '{target.requested_provider}'. Installed alias candidates: {', '.join(alias_candidates)}."
            )
        return (
            f"Requested model '{target.requested_model}' was not found in installed model inventory for "
            f"provider '{target.requested_provider}'."
        )
    if target.requested_provider == "lmstudio" and target.requested_model not in loaded_after:
        if auto_load_local_model:
            return (
                f"Requested model '{target.requested_model}' is installed for provider "
                f"'{target.requested_provider}' but could not be loaded into the active runtime."
            )
        return (
            f"Requested model '{target.requested_model}' is installed for provider "
            f"'{target.requested_provider}' but auto-load is disabled."
        )
    return (
        f"Requested model '{target.requested_model}' could not be resolved for provider "
        f"'{target.requested_provider}' (resolution_mode={resolution_mode or 'unknown'})."
    )


def _inventory_row(
    *,
    target: InventoryTarget,
    timeout_sec: float,
    model_load_timeout_sec: float,
    model_ttl_sec: int,
    auto_load_local_model: bool,
) -> dict[str, Any]:
    attempted_candidates: list[dict[str, Any]] = []
    runtime_payload: dict[str, Any] | None = None
    blocking_error: str | None = None
    for candidate in target.provider_model_candidates:
        try:
            candidate_payload = warmup_provider_model(
                provider=target.requested_provider,
                requested_model=candidate,
                base_url=None,
                timeout_s=float(timeout_sec),
                auto_select_model=False,
                auto_load_local_model=bool(auto_load_local_model),
                model_load_timeout_s=float(model_load_timeout_sec),
                model_ttl_sec=int(model_ttl_sec),
            )
            candidate_error = _blocking_error(
                target=target,
                runtime_payload=candidate_payload,
                auto_load_local_model=bool(auto_load_local_model),
            )
        except ProviderRuntimeWarmupError as exc:
            candidate_payload = {
                "requested_provider": target.requested_provider,
                "canonical_provider": "",
                "requested_model": candidate,
                "model_id": "",
                "base_url": "",
                "resolution_mode": "warmup_failed",
                "inventory_source": "warmup_exception",
                "available_models": [],
                "loaded_models_before": [],
                "loaded_models_after": [],
                "auto_load_attempted": bool(auto_load_local_model and target.requested_provider == "lmstudio"),
                "auto_load_performed": False,
                "status": "BLOCKED",
            }
            candidate_error = str(exc)
        attempted_candidates.append(
            {
                "candidate_model": candidate,
                "status": str(candidate_payload.get("status") or "BLOCKED"),
                "resolution_mode": str(candidate_payload.get("resolution_mode") or ""),
                "resolved_model": str(candidate_payload.get("resolved_model") or candidate_payload.get("model_id") or ""),
                "blocking_error": candidate_error,
            }
        )
        if runtime_payload is None:
            runtime_payload = candidate_payload
            blocking_error = candidate_error
        if str(candidate_payload.get("status") or "").upper() == "OK":
            runtime_payload = candidate_payload
            blocking_error = None
            break

    if runtime_payload is None:
        runtime_payload = {
            "requested_provider": target.requested_provider,
            "canonical_provider": "",
            "requested_model": target.requested_model,
            "model_id": "",
            "base_url": "",
            "resolution_mode": "warmup_failed",
            "inventory_source": "warmup_exception",
            "available_models": [],
            "loaded_models_before": [],
            "loaded_models_after": [],
            "auto_load_attempted": bool(auto_load_local_model and target.requested_provider == "lmstudio"),
            "auto_load_performed": False,
            "status": "BLOCKED",
        }
        blocking_error = "No candidate models were attempted."

    requested_runtime_model = str(runtime_payload.get("requested_model") or target.requested_model)
    alias_resolution = "canonical"
    if requested_runtime_model and requested_runtime_model != target.requested_model:
        alias_resolution = "explicit_alias_candidate"

    return {
        **target.to_payload(),
        "alias_resolution": alias_resolution,
        "runtime_target": {
            "requested_provider": str(runtime_payload.get("requested_provider") or target.requested_provider),
            "canonical_provider": str(runtime_payload.get("canonical_provider") or ""),
            "requested_model": requested_runtime_model,
            "resolved_model": str(runtime_payload.get("resolved_model") or runtime_payload.get("model_id") or ""),
            "base_url": str(runtime_payload.get("base_url") or ""),
            "resolution_mode": str(runtime_payload.get("resolution_mode") or ""),
            "inventory_source": str(runtime_payload.get("inventory_source") or ""),
            "status": str(runtime_payload.get("status") or "BLOCKED"),
            "auto_load_attempted": bool(runtime_payload.get("auto_load_attempted", False)),
            "auto_load_performed": bool(runtime_payload.get("auto_load_performed", False)),
        },
        "attempted_candidates": attempted_candidates,
        "installed_models": [str(model) for model in (runtime_payload.get("available_models") or []) if str(model).strip()],
        "loaded_models_before": [
            str(model) for model in (runtime_payload.get("loaded_models_before") or []) if str(model).strip()
        ],
        "loaded_models_after": [
            str(model) for model in (runtime_payload.get("loaded_models_after") or []) if str(model).strip()
        ],
        "blocking_error": blocking_error,
    }


def _lane_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_role = {str(row.get("role") or ""): row for row in rows}
    quality_ok = str((by_role.get("proposer_quality") or {}).get("runtime_target", {}).get("status") or "") == "OK"
    portability_ok = (
        str((by_role.get("proposer_portability") or {}).get("runtime_target", {}).get("status") or "") == "OK"
    )
    judge_primary_ok = str((by_role.get("judge_primary") or {}).get("runtime_target", {}).get("status") or "") == "OK"
    judge_fallback_ok = str((by_role.get("judge_fallback") or {}).get("runtime_target", {}).get("status") or "") == "OK"
    judge_path = "blocked"
    if judge_primary_ok:
        judge_path = "primary"
    elif judge_fallback_ok:
        judge_path = "fallback"

    observed_path = "primary"
    observed_result = "success"
    lane_readiness = "ready"
    note = "Quality proposer, portability proposer, and primary FunctionGemma judge are all available."
    blockers: list[dict[str, str]] = []

    for row in rows:
        blocking_error = str(row.get("blocking_error") or "").strip()
        if blocking_error:
            blockers.append({"role": str(row.get("role") or ""), "detail": blocking_error})

    if not portability_ok or judge_path == "blocked":
        observed_path = "blocked"
        observed_result = "environment blocker"
        lane_readiness = "blocked"
        note = "The lane cannot execute because the portability proposer or every admitted judge path is blocked."
    elif not quality_ok:
        observed_path = "degraded"
        observed_result = "partial success"
        lane_readiness = "degraded"
        note = "The portability proposer and at least one judge path are available, but the 12B quality target is blocked."
    elif judge_path == "fallback":
        observed_path = "fallback"
        observed_result = "partial success"
        lane_readiness = "degraded"
        note = "The lane is executable, but only the fallback FunctionGemma judge path is available."

    return {
        "lane_readiness": lane_readiness,
        "judge_path": judge_path,
        "quality_target_available": quality_ok,
        "portability_target_available": portability_ok,
        "judge_primary_available": judge_primary_ok,
        "judge_fallback_available": judge_fallback_ok,
        "observed_path": observed_path,
        "observed_result": observed_result,
        "note": note,
        "blocking_roles": blockers,
    }


def run_inventory(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(str(args.repo_root)).resolve()
    rows = [
        _inventory_row(
            target=target,
            timeout_sec=float(args.timeout_sec),
            model_load_timeout_sec=float(args.model_load_timeout_sec),
            model_ttl_sec=int(args.model_ttl_sec),
            auto_load_local_model=bool(args.auto_load_local_model),
        )
        for target in INVENTORY_TARGETS
    ]
    summary = _lane_summary(rows)
    out_path = _resolve_repo_path(repo_root, str(args.out))
    return {
        "schema_version": "prompt_reforger_gemma_tool_use_inventory.v1",
        "generated_at_utc": _now_utc_iso(),
        "proof_type": "live",
        "observed_path": summary["observed_path"],
        "observed_result": summary["observed_result"],
        "lane_readiness": summary["lane_readiness"],
        "implementation_plan_ref": IMPLEMENTATION_PLAN_REF,
        "canonical_commands": {
            "runtime_inventory": f"python {RUNTIME_INVENTORY_SCRIPT}",
            "bootstrap_harness": f"python {BOOTSTRAP_HARNESS_SCRIPT}",
        },
        "canonical_output_paths": {
            "runtime_inventory": _relativize(out_path, repo_root),
            "bootstrap_harness": BOOTSTRAP_HARNESS_OUTPUT,
        },
        "judge_quant_guidance": _judge_quant_guidance(),
        "bootstrap_proof_slice": _bootstrap_proof_slice(),
        "inventory_targets": rows,
        "summary": summary,
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = Path(str(args.repo_root)).resolve()
    out_path = _resolve_repo_path(repo_root, str(args.out))
    payload = run_inventory(args)
    write_payload_with_diff_ledger(out_path, payload)
    print(
        json.dumps(
            {
                "lane_readiness": str(payload.get("lane_readiness") or ""),
                "observed_path": str(payload.get("observed_path") or ""),
                "observed_result": str(payload.get("observed_result") or ""),
                "out": _relativize(out_path, repo_root),
            }
        )
    )
    return 0 if str(payload.get("observed_path") or "") != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
