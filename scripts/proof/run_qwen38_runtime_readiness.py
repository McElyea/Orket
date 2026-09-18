"""Live bounded cache, stop, sampling, cancellation and tokenizer proof for Qwen3.8."""

# ruff: noqa: E402 -- direct script execution requires the repository import root.
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from orket.adapters.llm.llama_cpp_render_verification import expected_text_render
from orket.adapters.llm.local_model_provider import LocalModelProvider
from orket.application.services.local_model_factory import create_local_model_provider
from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_MODEL
from orket.exceptions import ModelProviderError
from orket.runtime.config.local_prompt_profiles import (
    DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH,
    load_local_prompt_profile_registry_file,
)
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger

OUTPUT = ROOT / "benchmarks/results/protocol/local_prompting/qwen38_promotion/runtime_readiness.json"


def native_call(client: httpx.Client, messages: list[dict[str, str]], **options) -> dict:
    response = client.post(
        "/completion",
        json={
            "prompt": expected_text_render(messages),
            "temperature": 0,
            "n_predict": 64,
            "cache_prompt": True,
            **options,
        },
    )
    response.raise_for_status()
    result = response.json()
    return {key: value for key, value in result.items() if key != "prompt"}


def stop_and_sampling(client: httpx.Client, profile) -> list[dict]:
    rows = []
    for task in ("strict_json", "tool_call", "concise_text", "reasoning"):
        bundle = profile.sampling_bundles[task].model_dump()
        sentinel = profile.stop_sequences_by_task_class[task][0]
        # For template EOS tasks use normal EOG; structured tasks exercise explicit sentinels.
        text = (
            f"Output exactly: ALPHA{sentinel}OMEGA" if task in {"strict_json", "tool_call"} else "Output exactly ALPHA"
        )
        messages = [{"role": "user", "content": text}]
        options = {
            "temperature": bundle["temperature"],
            "top_p": bundle["top_p"],
            "top_k": bundle["top_k"],
            "repeat_penalty": bundle["repeat_penalty"],
            "seed": bundle["seed_value"] or 101,
            "n_predict": 64,
        }
        result = native_call(client, messages, stop=profile.stop_sequences_by_task_class[task], **options)
        settings = result["generation_settings"]
        applied = all(
            abs(float(settings[key]) - float(options[key])) < 1e-6
            for key in ("temperature", "top_p", "top_k", "repeat_penalty", "seed", "n_predict")
        )
        stop_ok = result.get("stop_type") in {"word", "eos"} and result["content"].strip() == "ALPHA"
        counterfactual = None
        if task in {"strict_json", "tool_call"}:
            counterfactual = native_call(client, messages, stop=[], **options)
            stop_ok = stop_ok and result.get("stopping_word") == sentinel and "OMEGA" in counterfactual["content"]
        rows.append(
            {
                "task_class": task,
                "passed": bool(applied and stop_ok),
                "sampling_evidence": "server_effective_settings",
                "result": result,
                "without_sentinel_stop": counterfactual,
            }
        )
    return rows


def cache_and_cancel(client: httpx.Client) -> dict:
    prefix = "Shared reference: " + "amber blue cedar delta " * 128
    rows = []
    for index in (0, 0, 1, 0, 2, 2):
        messages = [{"role": "system", "content": prefix}, {"role": "user", "content": f"Reply exactly VALUE{index}"}]
        result = native_call(client, messages)
        rows.append({"index": index, "passed": result["content"].strip() == f"VALUE{index}", "result": result})
    received = False
    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": DEFAULT_LOCAL_MODEL,
            "stream": True,
            "messages": [{"role": "user", "content": "Count from 1 to 1000, one number per line."}],
            "max_tokens": 512,
        },
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line.startswith("data: ") and line[6:] != "[DONE]":
                chunk = json.loads(line[6:])
                if chunk["choices"][0].get("delta", {}).get("content"):
                    received = True
                    break
    recovery = native_call(client, [{"role": "user", "content": "Reply exactly RECOVERED"}])
    health = client.get("/health")
    return {
        "cases": rows,
        "cache_reuse_observed": any(row["result"]["timings"]["cache_n"] > 0 for row in rows),
        "cancelled_after_content": received,
        "recovery": recovery,
        "health_status": health.status_code,
        "passed": all(row["passed"] for row in rows)
        and received
        and recovery["content"].strip() == "RECOVERED"
        and health.status_code == 200,
    }


def must_stop_cases(client: httpx.Client) -> list[dict]:
    rows = []
    for sentinel in ("<|json_end|>", "<|tool_end|>"):
        messages = [
            {
                "role": "user",
                "content": f"Repeat this string continuously with no preface or separators until the output limit: ALPHA{sentinel}OMEGA",
            }
        ]
        stopped = native_call(client, messages, stop=[sentinel], n_predict=64)
        unbounded_request = native_call(client, messages, stop=[], n_predict=64)
        rows.append(
            {
                "sentinel": sentinel,
                "stopped": stopped,
                "bounded_counterfactual": unbounded_request,
                "passed": stopped.get("stop_type") == "word"
                and stopped.get("stopping_word") == sentinel
                and unbounded_request.get("stop_type") == "limit",
            }
        )
    return rows


async def adapter_cases() -> list[dict]:
    client = create_local_model_provider(model=DEFAULT_LOCAL_MODEL, provider="llama_cpp")
    rows = []
    try:
        for task in ("strict_json", "tool_call", "concise_text", "reasoning"):
            response = await client.complete(
                [{"role": "user", "content": 'Return only {"ok":true}'}],
                runtime_context={
                    "protocol_governed_enabled": True,
                    "local_prompt_task_class": task,
                    "local_prompting_mode": "enforce",
                    "local_prompt_max_output_tokens": 64,
                },
            )
            raw = response.raw
            rows.append(
                {
                    "task_class": task,
                    "response": response.content,
                    "metadata": raw,
                    "passed": json.loads(response.content) == {"ok": True}
                    and raw.get("render_verified")
                    and raw.get("token_counter_source") == "llama_cpp_native_tokenize",
                }
            )
        rows.extend(await role_and_budget_cases(client))
    finally:
        await client.close()
    return rows


async def role_and_budget_cases(client: LocalModelProvider) -> list[dict]:
    context = {
        "protocol_governed_enabled": True,
        "local_prompt_task_class": "tool_call",
        "local_prompting_mode": "enforce",
        "local_prompt_max_output_tokens": 64,
    }
    messages = [
        {"role": "system", "content": "Return the tool's JSON result exactly."},
        {"role": "user", "content": "Read the status."},
        {"role": "assistant", "content": '{"tool":"read_status","args":{}}'},
        {"role": "tool", "content": '{"ok":true}'},
        {"role": "user", "content": "Return that result now, JSON only."},
    ]
    response = await client.complete(messages, runtime_context=context)
    rows = [
        {
            "task_class": "tool_role_history",
            "response": response.content,
            "metadata": response.raw,
            "passed": json.loads(response.content) == {"ok": True} and response.raw.get("render_verified"),
        }
    ]
    try:
        await client.complete([{"role": "user", "content": " x" * 9000}], runtime_context=context)
    except ModelProviderError as exc:
        rows.append(
            {
                "task_class": "native_token_budget_refusal",
                "error": str(exc),
                "passed": "E_LLAMA_CPP_CONTEXT_BUDGET" in str(exc),
            }
        )
    else:
        rows.append({"task_class": "native_token_budget_refusal", "passed": False})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    args = parser.parse_args()
    os.environ["ORKET_DISABLE_SANDBOX"] = "1"
    os.environ["ORKET_LLM_LLAMA_CPP_BASE_URL"] = args.base_url.rstrip("/") + "/v1"
    registry = load_local_prompt_profile_registry_file(DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH)
    profile = registry.resolve_profile(provider="llama_cpp", model=DEFAULT_LOCAL_MODEL).profile
    with httpx.Client(base_url=args.base_url, timeout=120) as client:
        props = client.get("/props").json()
        stops = stop_and_sampling(client, profile)
        must_stop = must_stop_cases(client)
        cache = cache_and_cancel(client)
    adapters = asyncio.run(adapter_cases())
    passed = (
        all(row["passed"] for row in stops + adapters + must_stop) and cache["passed"] and cache["cache_reuse_observed"]
    )
    model_path = Path(props["model_path"])
    with model_path.open("rb") as source:
        model_sha256 = hashlib.file_digest(source, "sha256").hexdigest()
    payload = {
        "schema_version": "qwen38_runtime_readiness.v1",
        "proof_mode": "live",
        "observed_path": "primary",
        "observed_result": "success" if passed else "failure",
        "server_build": props["build_info"],
        "model": DEFAULT_LOCAL_MODEL,
        "model_path": str(model_path),
        "model_sha256": model_sha256,
        "template_sha256": hashlib.sha256(props["chat_template"].encode()).hexdigest(),
        "stop_and_sampling": stops,
        "must_stop": must_stop,
        "cache_and_cancellation": cache,
        "adapter_cases": adapters,
        "limits": [
            "Bounded single-slot text workload; no unbounded soak, native tools or arbitrary-objective claim.",
            "Effective sampler settings are server-reported; output distributions are not benchmarked.",
        ],
    }
    write_payload_with_diff_ledger(OUTPUT, payload)
    print(json.dumps({"output": str(OUTPUT), "observed_result": payload["observed_result"]}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
