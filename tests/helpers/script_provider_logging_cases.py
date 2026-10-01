"""Inputs and controlled responses for real standalone script/provider execution."""
from __future__ import annotations

import json
from pathlib import Path

from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_MODEL
from orket.kernel.v1.odr.core import ReactorConfig
from scripts.audit.replay_turn import _default_replay_call
from scripts.odr import model_runtime_control, run_odr_live_role_matrix
from scripts.odr.provider_admission import ProviderSelection
from scripts.probes import p02_odr_isolation
from scripts.prompt_lab import guide_model_prompt_patch, run_functiongemma_tool_call_judge
from scripts.proof import run_qwen38_repair_readiness, run_qwen38_runtime_readiness
from scripts.protocol.local_prompting_conformance_runner import run_cases
from scripts.workloads import code_review_probe
from scripts.workloads.workload_support import run_strict_json_model

ROOT = Path(__file__).resolve().parents[2]
CALLERS = ("strict-json", "replay", "conformance", "transient", "role-matrix", "guide", "judge",
           "code-review", "runtime-readiness", "repair-readiness", "p02")


def model_for(caller):
    return DEFAULT_LOCAL_MODEL if caller.endswith("readiness") else "fixture-qwen-logging-retry"


def _judge_packet():
    packet = {key: [] for key in ("diagnostics", "required_action_tools", "required_read_paths",
        "required_write_paths", "required_statuses", "messages", "parsed_tool_calls", "accepted_tool_calls",
        "rejected_tool_calls", "argument_shape_defects")}
    packet.update({key: "fixture" for key in ("slice_id", "issue_id", "role_name", "turn_dir", "description",
        "messages_ref", "model_response_raw_ref", "parsed_tool_calls_ref")})
    return {**packet, "turn_index": 1, "model_response_raw": {}, "valid_completion": False}


async def invoke_script(caller, root, url):
    model = model_for(caller)
    messages = [{"role": "user", "content": "Return a JSON object."}]
    if caller == "replay":
        return await _default_replay_call(messages=messages, model=model, runtime_context={})
    if caller == "strict-json":
        return await run_strict_json_model(model=model, provider="openai_compat", ollama_host="",
            temperature=0, seed=0, timeout=30, messages=messages)
    if caller == "conformance":
        return await run_cases(provider="openai_compat", model=model, profile_id="fixture", task_class="strict_json",
            case_ids=["one"], threshold=1, lmstudio_session_mode="none", lmstudio_session_id="", mock=False)
    if caller == "transient":
        return await model_runtime_control.complete_with_transient_provider(model=model, messages=messages,
            temperature=0, timeout=30, provider_name="openai_compat", base_url=url + "/v1")
    if caller == "role-matrix":
        return await run_odr_live_role_matrix._run_pairing(pairing=run_odr_live_role_matrix.Pairing(model, model),
            scenario_inputs=[{"id": "logging", "R0": "Observe retry logging", "A0": [], "seed": {}}],
            rounds=1, odr_cfg=ReactorConfig(), temperature=0, model_timeout=30,
            provider_selection=ProviderSelection("openai_compat", url + "/v1"))
    if caller == "guide":
        return await guide_model_prompt_patch._invoke_guide_model(
            guide_spec=guide_model_prompt_patch.GuideModelSpec("fixture", "openai_compat", model, url + "/v1"),
            runtime_payload={}, packet={}, timeout_sec=30, max_prompt_patch_chars=100)
    if caller == "judge":
        target = run_functiongemma_tool_call_judge.JudgeTarget("judge", "openai_compat", model,
            url + "/v1", "fixture", "primary", "exact", model)
        return await run_functiongemma_tool_call_judge._run_judgments(target=target, packets=[_judge_packet()], timeout_sec=30)
    if caller == "code-review":
        args = code_review_probe._parse_args(["--model", model, "--provider", "openai_compat", "--timeout", "30",
            "--fixture", str(ROOT / code_review_probe.DEFAULT_FIXTURE),
            "--answer-key", str(ROOT / code_review_probe.DEFAULT_ANSWER_KEY), "--workspace", str(root / "review")])
        return await code_review_probe._run_probe(args)
    if caller == "runtime-readiness":
        return await run_qwen38_runtime_readiness.adapter_cases()
    if caller == "repair-readiness":
        return await run_qwen38_repair_readiness.prove()
    if caller == "p02":
        args = p02_odr_isolation._parse_args(["--model", model, "--provider", "openai_compat",
                                            "--runs", "1", "--max-rounds", "1", "--timeout", "30"])
        return await p02_odr_isolation._run_probe(args)
    raise AssertionError(caller)


def response_content(caller, successful_index):
    if caller == "repair-readiness":
        return ('```json\n{"content":"","tool_calls":[]}\n```' if successful_index == 1
                else '{"content":"","tool_calls":[]}')
    if caller == "conformance":
        return '{"ok":true,"case_id":"one"}'
    if caller == "code-review":
        return '{"summary":["Controlled fixture"],"high_risk_issues":[],"missing_tests":[]}'
    return '{"ok":true}'


def assert_result(caller, result, recover):
    if not recover:
        if caller == "guide":
            assert result[:2] == ("blocked", "environment blocker")
            assert "failed after 3 attempts" in result[-1]
        else:
            assert caller == "judge"
            assert "failed after 3 attempts" in result[0]["judge_response"]["raw"]["error"]
        return
    if caller in {"strict-json", "replay", "transient"}:
        content = result["content"] if caller == "replay" else (
            result[0].content if caller == "transient" else result[0])
        assert json.loads(content) == {"ok": True}
    elif caller == "conformance":
        assert result["strict_ok"] and result["pass_cases"] == 1
    elif caller == "role-matrix":
        assert len(result["scenarios"][0]["rounds"]) == 1
    elif caller == "guide":
        assert result[:2] == ("degraded", "partial success") and result[4] == {"ok": True}
    elif caller == "judge":
        assert json.loads(result[0]["judge_response"]["content"]) == {"ok": True}
    elif caller == "code-review":
        assert result["probe_status"] == "observed" and result["review_contract"]["contract_valid"]
        assert result["artifact_bundle"]["files"]
    elif caller == "runtime-readiness":
        assert len(result) == 6 and all(row["passed"] for row in result)
    elif caller == "p02":
        assert result["runs_requested"] == 1 and len(result["results"]) == 1
        assert result["results"][0]["model"] == model_for(caller) and result["results"][0]["raw_signature"]
    else:
        assert caller == "repair-readiness" and result["passed"] and result["deterministic_reprompt"]
