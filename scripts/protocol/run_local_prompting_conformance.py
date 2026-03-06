from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import random
import sys
from typing import Any
try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from orket.adapters.llm.local_model_provider import LocalModelProvider
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
    parser.add_argument("--out-root", default="benchmarks/results/protocol/local_prompting", help="Artifact output root")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on threshold failure")
    parser.add_argument("--mock", action="store_true", help="Use deterministic mock responses instead of live provider calls")
    return parser
def _prompt_for_case(task_class: str, case_id: str) -> str:
    if task_class == "tool_call":
        return (
            "Return ONLY this JSON object with no prose or markdown: "
            f'{{"tool":"read_file","args":{{"path":"README.md","case_id":"{case_id}"}}}}'
        )
    return f'Return ONLY this JSON object with no prose or markdown: {{"ok":true,"case_id":"{case_id}"}}'
def _validate_case(task_class: str, content: str, case_id: str) -> tuple[bool, str]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return False, "JSON_PARSE_ERROR"
    if not isinstance(payload, dict):
        return False, "SCHEMA_MISMATCH"
    if task_class == "tool_call":
        tool = str(payload.get("tool") or "").strip()
        args = payload.get("args")
        if not tool or not isinstance(args, dict):
            return False, "TOOL_SHAPE_INVALID"
        return True, ""
    ok = payload.get("ok")
    parsed_case_id = str(payload.get("case_id") or "").strip()
    if ok is not True or parsed_case_id != case_id:
        return False, "SCHEMA_MISMATCH"
    return True, ""
def _mock_content(task_class: str, case_id: str) -> str:
    if task_class == "tool_call":
        return json.dumps({"tool": "read_file", "args": {"path": "README.md", "case_id": case_id}})
    return json.dumps({"ok": True, "case_id": case_id})
def _resolve_case_counts(args: argparse.Namespace) -> tuple[int, int]:
    if str(args.suite) == "promotion":
        strict_default = 1000
        tool_default = 500
    else:
        strict_default = max(1, int(args.cases))
        tool_default = max(1, int(args.cases))
    strict_count = max(1, int(args.strict_json_cases)) if int(args.strict_json_cases) > 0 else strict_default
    tool_count = max(1, int(args.tool_call_cases)) if int(args.tool_call_cases) > 0 else tool_default
    return strict_count, tool_count
def _anti_meta_flags(content: str) -> dict[str, bool]:
    markdown_fence = "```" in content
    trimmed = str(content or "").strip(" \t\r\n")
    if not trimmed:
        return {"markdown_fence": markdown_fence, "protocol_chatter": True}
    decoder = json.JSONDecoder()
    try:
        _, end_pos = decoder.raw_decode(trimmed)
        remainder = trimmed[end_pos:].strip(" \t\r\n")
        return {"markdown_fence": markdown_fence, "protocol_chatter": bool(remainder)}
    except json.JSONDecodeError:
        return {"markdown_fence": markdown_fence, "protocol_chatter": True}
async def _run_cases(
    *,
    provider: str,
    model: str,
    profile_id: str,
    task_class: str,
    case_ids: list[str],
    threshold: float,
    mock: bool,
) -> dict[str, Any]:
    provider_client = None if mock else LocalModelProvider(model=model, temperature=0.0, timeout=90)
    failures: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    render_hashes: list[str] = []
    telemetry_samples: list[dict[str, Any]] = []
    anti_meta_counts = {"markdown_fence": 0, "protocol_chatter": 0}
    for case_id in case_ids:
        if mock:
            content = _mock_content(task_class, case_id)
            raw: dict[str, Any] = {
                "profile_id": profile_id,
                "task_class": task_class,
                "template_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "template_hash_alg": "sha256",
            }
        else:
            assert provider_client is not None
            response = await provider_client.complete(
                [{"role": "user", "content": _prompt_for_case(task_class, case_id)}],
                runtime_context={
                    "protocol_governed_enabled": task_class in {"strict_json", "tool_call"},
                    "local_prompt_task_class": task_class,
                    "local_prompting_mode": "enforce",
                },
            )
            content = str(response.content or "")
            raw = dict(response.raw or {})
        passed, failure = _validate_case(task_class, content, case_id)
        if not passed:
            failures[failure] = failures.get(failure, 0) + 1
        anti_meta = _anti_meta_flags(content)
        if anti_meta["markdown_fence"]:
            anti_meta_counts["markdown_fence"] += 1
        if anti_meta["protocol_chatter"]:
            anti_meta_counts["protocol_chatter"] += 1
        rows.append(
            {
                "case_id": case_id,
                "passed": passed,
                "failure_family": failure or None,
                "response_chars": len(content),
                "anti_meta": anti_meta,
            }
        )
        render_hash = str(raw.get("template_hash") or "")
        if render_hash:
            render_hashes.append(render_hash)
        telemetry_samples.append(
            {
                "profile_id": str(raw.get("profile_id") or ""),
                "task_class": str(raw.get("task_class") or ""),
                "template_hash_alg": str(raw.get("template_hash_alg") or ""),
                "effective_stop_sequences": list(raw.get("effective_stop_sequences") or []),
                "sampling_bundle": dict(raw.get("sampling_bundle") or {}),
            }
        )
    pass_count = sum(1 for row in rows if row["passed"])
    total = len(rows)
    pass_rate = float(pass_count) / float(max(1, total))
    return {
        "schema_version": f"local_prompting_conformance.{task_class}.v1",
        "provider": provider,
        "model": model,
        "profile_id": profile_id,
        "task_class": task_class,
        "total_cases": total,
        "pass_cases": pass_count,
        "pass_rate": round(pass_rate, 6),
        "threshold": threshold,
        "strict_ok": pass_rate >= threshold,
        "failure_families": failures,
        "case_results": rows,
        "render_hash_samples": sorted(set(render_hashes))[:20],
        "telemetry_samples": telemetry_samples[:20],
        "anti_meta_counts": anti_meta_counts,
    }
def _write_json(path: Path, payload: dict[str, Any]) -> None:
    write_payload_with_diff_ledger(path, payload)
def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
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
    strict_json_case_count, tool_call_case_count = _resolve_case_counts(args)
    strict_json_case_ids = [
        f"strict-json-{index:04d}-{randomizer.randint(100, 999)}"
        for index in range(strict_json_case_count)
    ]
    tool_call_case_ids = [
        f"tool-call-{index:04d}-{randomizer.randint(100, 999)}"
        for index in range(tool_call_case_count)
    ]
    strict_json = asyncio.run(
        _run_cases(
            provider=provider,
            model=model,
            profile_id=profile_id,
            task_class="strict_json",
            case_ids=strict_json_case_ids,
            threshold=float(args.strict_json_threshold),
            mock=bool(args.mock),
        )
    )
    tool_call = asyncio.run(
        _run_cases(
            provider=provider,
            model=model,
            profile_id=profile_id,
            task_class="tool_call",
            case_ids=tool_call_case_ids,
            threshold=float(args.tool_call_threshold),
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
        "task_classes": ["strict_json", "tool_call"],
        "strict_json_case_ids": strict_json_case_ids,
        "tool_call_case_ids": tool_call_case_ids,
        "selection_seed": random_seed,
        "prompt_corpus_hash": _sha256_bytes(
            json.dumps(
                {
                    "strict_json_case_ids": strict_json_case_ids,
                    "tool_call_case_ids": tool_call_case_ids,
                },
                sort_keys=True,
            ).encode("utf-8")
        ),
        "profile_registry_snapshot_hash": _sha256_bytes(
            Path(DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH).read_bytes()
        ),
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
    _write_json(profile_root / "suite_manifest.json", suite_manifest)
    _write_json(profile_root / "tokenizer_identity.json", tokenizer_identity)
    registry_payload = json.loads(Path(DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH).read_text(encoding="utf-8"))
    _write_json(profiles_root / "profile_registry_snapshot.json", registry_payload)
    (profiles_root / "profile_registry_snapshot.sha256").write_text(
        _sha256_bytes(Path(DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH).read_bytes()) + "\n",
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
    strict_ok = bool(strict_json["strict_ok"]) and bool(tool_call["strict_ok"]) and bool(anti_meta["strict_ok"])
    if bool(args.strict) and not strict_ok:
        return 1
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
