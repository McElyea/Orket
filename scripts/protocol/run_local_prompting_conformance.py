from __future__ import annotations
import argparse
import asyncio
import json
import os
from pathlib import Path
import random
import sys
from typing import Any
try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
    from scripts.protocol.local_prompting_conformance_helpers import resolve_case_counts, sha256_bytes
    from scripts.protocol.local_prompting_conformance_runner import run_cases
    from scripts.providers.lmstudio_model_cache import (
        LmStudioCacheClearError,
        clear_loaded_models,
        default_lmstudio_base_url,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger
    from protocol.local_prompting_conformance_helpers import resolve_case_counts, sha256_bytes
    from protocol.local_prompting_conformance_runner import run_cases
    from providers.lmstudio_model_cache import (
        LmStudioCacheClearError,
        clear_loaded_models,
        default_lmstudio_base_url,
    )
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from orket.runtime.error_codes import error_registry_snapshot
from orket.runtime.local_prompt_profiles import (
    DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH,
    load_local_prompt_profile_registry_file,
)
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local prompting conformance suites.")
    parser.add_argument("--provider", required=True, help="Provider backend: ollama/openai_compat/lmstudio")
    parser.add_argument("--model", required=True, help="Model id")
    parser.add_argument("--cases", type=int, default=10, help="Case count per task class")
    parser.add_argument("--strict-json-cases", type=int, default=0, help="Strict JSON case count override")
    parser.add_argument("--tool-call-cases", type=int, default=0, help="Tool-call case count override")
    parser.add_argument(
        "--suite",
        choices=["smoke", "promotion"],
        default="smoke",
        help="Conformance corpus size profile.",
    )
    parser.add_argument("--strict-json-threshold", type=float, default=0.98, help="Strict JSON pass-rate threshold")
    parser.add_argument("--tool-call-threshold", type=float, default=0.99, help="Tool-call pass-rate threshold")
    parser.add_argument(
        "--max-protocol-chatter-rate",
        type=float,
        default=0.02,
        help="Maximum allowed anti-meta protocol chatter rate.",
    )
    parser.add_argument(
        "--max-markdown-fence-rate",
        type=float,
        default=0.02,
        help="Maximum allowed anti-meta markdown-fence rate.",
    )
    parser.add_argument(
        "--lmstudio-session-mode",
        choices=["none", "context", "fixed"],
        default="none",
        help="LM Studio session mode for OpenAI-compatible runs.",
    )
    parser.add_argument(
        "--lmstudio-session-id",
        default="",
        help="Optional fixed LM Studio session id (used by fixed/context mode).",
    )
    parser.add_argument(
        "--sanitize-model-cache",
        dest="sanitize_model_cache",
        action="store_true",
        default=True,
        help="Unload all LM Studio model instances before and after this run (default: enabled).",
    )
    parser.add_argument(
        "--no-sanitize-model-cache",
        dest="sanitize_model_cache",
        action="store_false",
        help="Disable LM Studio model-cache sanitation for this run.",
    )
    parser.add_argument(
        "--lmstudio-base-url",
        default=default_lmstudio_base_url(),
        help="LM Studio base URL used for model-cache sanitation calls.",
    )
    parser.add_argument(
        "--lmstudio-timeout-sec",
        type=int,
        default=10,
        help="Timeout in seconds for LM Studio model-cache sanitation calls.",
    )
    parser.add_argument("--out-root", default="benchmarks/results/protocol/local_prompting", help="Artifact output root")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on threshold failure")
    parser.add_argument("--mock", action="store_true", help="Use deterministic mock responses instead of live provider calls")
    return parser
def _run_cache_sanitation(*, stage: str, enabled: bool, base_url: str, timeout_sec: int) -> dict[str, Any]:
    if not enabled:
        return {"stage": str(stage), "status": "NOT_APPLICABLE"}
    return clear_loaded_models(stage=str(stage), base_url=str(base_url), timeout_sec=int(timeout_sec), strict=True)
def _write_json(path: Path, payload: dict[str, Any]) -> None:
    write_payload_with_diff_ledger(path, payload)
def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    provider_raw = str(args.provider or "").strip().lower()
    provider = "openai_compat" if provider_raw == "lmstudio" else provider_raw
    model = str(args.model or "").strip()
    if provider not in {"ollama", "openai_compat"}:
        raise ValueError(f"unsupported provider '{provider_raw}'")
    if not model:
        raise ValueError("model is required")
    os.environ["ORKET_LLM_PROVIDER"] = provider_raw if provider_raw else provider
    sanitize_enabled = bool(args.sanitize_model_cache) and provider_raw == "lmstudio"
    sanitation_events: list[dict[str, Any]] = []
    post_sanitation_error = ""
    try:
        sanitation_events.append(
            _run_cache_sanitation(
                stage="pre_run",
                enabled=sanitize_enabled,
                base_url=str(args.lmstudio_base_url),
                timeout_sec=int(args.lmstudio_timeout_sec),
            )
        )
    except LmStudioCacheClearError as exc:
        raise SystemExit(str(exc)) from exc
    registry = load_local_prompt_profile_registry_file(DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH)
    resolved = registry.resolve_profile(provider=provider, model=model)
    profile_id = resolved.profile.profile_id
    out_root = Path(str(args.out_root)).resolve()
    profile_root = out_root / "conformance" / provider / profile_id
    profiles_root = out_root / "profiles"
    profile_root.mkdir(parents=True, exist_ok=True)
    profiles_root.mkdir(parents=True, exist_ok=True)
    random_seed = 1337
    randomizer = random.Random(random_seed)
    strict_json_case_count, tool_call_case_count = resolve_case_counts(
        suite=str(args.suite),
        cases=int(args.cases),
        strict_json_cases=int(args.strict_json_cases),
        tool_call_cases=int(args.tool_call_cases),
    )
    strict_json_case_ids = [
        f"strict-json-{index:04d}-{randomizer.randint(100, 999)}"
        for index in range(strict_json_case_count)
    ]
    tool_call_case_ids = [
        f"tool-call-{index:04d}-{randomizer.randint(100, 999)}"
        for index in range(tool_call_case_count)
    ]
    strict_json = asyncio.run(
        run_cases(
            provider=provider,
            model=model,
            profile_id=profile_id,
            task_class="strict_json",
            case_ids=strict_json_case_ids,
            threshold=float(args.strict_json_threshold),
            lmstudio_session_mode=str(args.lmstudio_session_mode),
            lmstudio_session_id=str(args.lmstudio_session_id or ""),
            mock=bool(args.mock),
        )
    )
    tool_call = asyncio.run(
        run_cases(
            provider=provider,
            model=model,
            profile_id=profile_id,
            task_class="tool_call",
            case_ids=tool_call_case_ids,
            threshold=float(args.tool_call_threshold),
            lmstudio_session_mode=str(args.lmstudio_session_mode),
            lmstudio_session_id=str(args.lmstudio_session_id or ""),
            mock=bool(args.mock),
        )
    )
    total_anti_meta_cases = int(strict_json["total_cases"]) + int(tool_call["total_cases"])
    protocol_chatter_count = int(strict_json["anti_meta_counts"]["protocol_chatter"]) + int(
        tool_call["anti_meta_counts"]["protocol_chatter"]
    )
    markdown_fence_count = int(strict_json["anti_meta_counts"]["markdown_fence"]) + int(
        tool_call["anti_meta_counts"]["markdown_fence"]
    )
    protocol_chatter_rate = float(protocol_chatter_count) / float(max(1, total_anti_meta_cases))
    markdown_fence_rate = float(markdown_fence_count) / float(max(1, total_anti_meta_cases))
    max_protocol_chatter_rate = float(args.max_protocol_chatter_rate)
    max_markdown_fence_rate = float(args.max_markdown_fence_rate)
    anti_meta = {
        "schema_version": "local_prompting_conformance.anti_meta.v1",
        "provider": provider,
        "model": model,
        "profile_id": profile_id,
        "suite": str(args.suite),
        "total_cases": total_anti_meta_cases,
        "protocol_chatter_count": protocol_chatter_count,
        "protocol_chatter_rate": round(protocol_chatter_rate, 6),
        "markdown_fence_count": markdown_fence_count,
        "markdown_fence_rate": round(markdown_fence_rate, 6),
        "max_protocol_chatter_rate": max_protocol_chatter_rate,
        "max_markdown_fence_rate": max_markdown_fence_rate,
        "strict_ok": protocol_chatter_rate <= max_protocol_chatter_rate and markdown_fence_rate <= max_markdown_fence_rate,
    }
    sampling_capabilities = {
        "schema_version": "local_prompting_sampling_capabilities.v1",
        "provider": provider,
        "model": model,
        "profile_id": profile_id,
        "task_classes": {
            "strict_json": strict_json["telemetry_samples"][0]["sampling_bundle"] if strict_json["telemetry_samples"] else {},
            "tool_call": tool_call["telemetry_samples"][0]["sampling_bundle"] if tool_call["telemetry_samples"] else {},
        },
        "field_capabilities": {
            "temperature": "honored",
            "top_p": "honored",
            "top_k": "provider_specific",
            "repeat_penalty": "provider_specific",
            "max_output_tokens": "honored",
            "seed": "honored",
        },
    }
    render_verification = {
        "schema_version": "local_prompting_render_verification.v1",
        "provider": provider,
        "model": model,
        "profile_id": profile_id,
        "method": "request_payload_hash",
        "template_hash_alg": "sha256",
        "strict_json_hash_samples": strict_json["render_hash_samples"],
        "tool_call_hash_samples": tool_call["render_hash_samples"],
    }
    capability_probe_method = {
        "schema_version": "local_prompting_capability_probe_method.v1",
        "provider": provider,
        "model": model,
        "profile_id": profile_id,
        "mode": "mock" if bool(args.mock) else "live",
        "method": "runtime_response_metadata",
    }
    suite_manifest = {
        "schema_version": "local_prompting_suite_manifest.v1",
        "provider": provider,
        "model": model,
        "profile_id": profile_id,
        "suite_version": "v1",
        "suite": str(args.suite),
        "lmstudio_session_mode": str(args.lmstudio_session_mode),
        "lmstudio_session_id_present": bool(str(args.lmstudio_session_id or "").strip()),
        "task_classes": ["strict_json", "tool_call"],
        "strict_json_case_ids": strict_json_case_ids,
        "tool_call_case_ids": tool_call_case_ids,
        "selection_seed": random_seed,
        "prompt_corpus_hash": sha256_bytes(
            json.dumps(
                {
                    "strict_json_case_ids": strict_json_case_ids,
                    "tool_call_case_ids": tool_call_case_ids,
                },
                sort_keys=True,
            ).encode("utf-8")
        ),
        "profile_registry_snapshot_hash": sha256_bytes(
            Path(DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH).read_bytes()
        ),
        "model_cache_sanitation": {
            "enabled": sanitize_enabled,
            "events": sanitation_events,
        },
    }
    tokenizer_identity = {
        "schema_version": "local_prompting_tokenizer_identity.v1",
        "provider": provider,
        "model": model,
        "profile_id": profile_id,
        "tokenizer_source": "profile_declared_equivalent",
        "history_policy": resolved.profile.history_policy,
    }
    _write_json(profile_root / "strict_json_report.json", strict_json)
    _write_json(profile_root / "tool_call_report.json", tool_call)
    _write_json(profile_root / "anti_meta_report.json", anti_meta)
    _write_json(profile_root / "sampling_capabilities.json", sampling_capabilities)
    _write_json(profile_root / "render_verification.json", render_verification)
    _write_json(profile_root / "capability_probe_method.json", capability_probe_method)
    _write_json(profile_root / "tokenizer_identity.json", tokenizer_identity)
    registry_payload = json.loads(Path(DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH).read_text(encoding="utf-8"))
    _write_json(profiles_root / "profile_registry_snapshot.json", registry_payload)
    (profiles_root / "profile_registry_snapshot.sha256").write_text(
        sha256_bytes(Path(DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH).read_bytes()) + "\n",
        encoding="utf-8",
    )
    _write_json(
        profiles_root / "enabled_pack.json",
        {
            "schema_version": "local_prompting_enabled_pack.v1",
            "pack_id": "pack_local_v1",
            "profiles": [profile_id],
        },
    )
    _write_json(profiles_root / "error_code_registry_snapshot.json", error_registry_snapshot())
    try:
        sanitation_events.append(
            _run_cache_sanitation(
                stage="post_run",
                enabled=sanitize_enabled,
                base_url=str(args.lmstudio_base_url),
                timeout_sec=int(args.lmstudio_timeout_sec),
            )
        )
    except LmStudioCacheClearError as exc:
        if isinstance(exc.result, dict) and exc.result:
            sanitation_events.append(exc.result)
        post_sanitation_error = str(exc)
    _write_json(profile_root / "suite_manifest.json", suite_manifest)
    strict_ok = bool(strict_json["strict_ok"]) and bool(tool_call["strict_ok"]) and bool(anti_meta["strict_ok"]) and not post_sanitation_error
    if post_sanitation_error:
        print(post_sanitation_error)
    if bool(args.strict) and not strict_ok:
        return 1
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
