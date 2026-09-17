"""Native ODR CLI with real local HTTP and files; provider responses are fixtures."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys

import pytest

from orket.adapters.llm.local_model_provider import LocalModelProvider
from scripts.odr import run_odr_live_role_matrix as live_matrix
from scripts.odr.provider_admission import ProviderSelection
from scripts.odr.run_arbiter import ArbiterFailure, RunArbiter
from tests.helpers.odr_provider_server import MODEL, provider_server

pytestmark = pytest.mark.integration


def native_sweep(folder, endpoint, *, model=MODEL, python_bin=None, provider="openai_compat", spec_mode="valid", extra_args=()):
    folder.mkdir(parents=True, exist_ok=True)
    spec = folder / "spec.json"
    if spec_mode != "missing":
        spec.write_text("{invalid" if spec_mode == "invalid" else json.dumps(
            {"config": {"rounds": 1, "scenario_ids": ["missing_constraint"], "timeout": 30}}), encoding="utf-8")
    env = dict(os.environ, ORKET_DISABLE_SANDBOX="1", ORKET_LLM_PROVIDER="ollama",
        ORKET_LLM_OLLAMA_HOST="http://127.0.0.1:1", ORKET_LOCAL_PROMPTING_MODE="shadow",
        ORKET_LLM_OPENAI_API_KEY="", ORKET_MODEL_STREAM_OPENAI_API_KEY="")
    command = [sys.executable, "scripts/odr/run_odr_quant_sweep.py", "--base-spec", str(spec),
        "--architect-models", model, "--auditor-models", model, "--out-dir", str(folder / "out"),
        "--index-out", str(folder / "out/index.json"), "--provenance-out", "", "--no-provenance-probes",
        "--provider", provider, "--base-url", endpoint]
    if python_bin:
        command.extend(["--python-bin", str(python_bin)])
    command.extend(extra_args)
    result = subprocess.run(command, env=env, capture_output=True, text=True, encoding="utf-8", timeout=90)
    (folder / "stdout.txt").write_text(result.stdout, encoding="utf-8")
    (folder / "stderr.txt").write_text(result.stderr, encoding="utf-8")
    return result


@pytest.mark.parametrize("mode", ["success", "missing", "unavailable", "inference-failure"])
# Layer: integration
def test_native_odr_provider_selection_and_refusal(tmp_path, mode):
    with provider_server(mode=mode) as (endpoint, calls):
        result = native_sweep(tmp_path, endpoint)
    plan = json.loads((tmp_path / "out/arbiter_plan.json").read_text(encoding="utf-8"))
    assert plan["schema_version"] == "odr.run_arbiter.plan.v2"
    assert plan["provider_selection"] == {"provider": "openai_compat", "base_url": endpoint}
    assert not any(m["kind"] == "tool" and m["value"] == "ollama" for m in plan["required_materials"])
    posts = [row for row in calls if row[0] == "POST"]
    if mode == "success":
        assert result.returncode == 0, result.stdout + result.stderr
        assert len(posts) == 2 and all(row[2]["model"] == MODEL for row in posts)
        architect_messages, auditor_messages = [row[2]["messages"] for row in posts]
        assert "Put all required behavior, bounds, and controls in REQUIREMENT." in architect_messages[0]["content"]
        assert "Reject demotion of required behavior" in auditor_messages[0]["content"]
        for messages in (architect_messages, auditor_messages):
            assert "250 words" in messages[0]["content"] and "DECISION_REQUIRED" in messages[0]["content"]
            assert "missing_constraint" in messages[1]["content"] and "Seed decisions:" in messages[1]["content"]
            assert "Initial auditor issues:" in messages[1]["content"] and "orket-constraints" in messages[1]["content"]
        index = json.loads((tmp_path / "out/index.json").read_text(encoding="utf-8"))
        assert index["run_count"] == 1
        run_path, = (tmp_path / "out").glob("odr_live_role_matrix.*.json")
        run = json.loads(run_path.read_text(encoding="utf-8"))
        assert run["config"]["provider_selection"] == plan["provider_selection"]
        assert run["diff_ledger"] and plan["diff_ledger"]
    else:
        assert result.returncode == 2, result.stdout + result.stderr
        error = json.loads((tmp_path / "out/arbiter_error.json").read_text(encoding="utf-8"))
        assert error["phase"] == ("execution" if mode == "inference-failure" else "preflight")
        assert error["diff_ledger"] and not (tmp_path / "out/index.json").exists()
        assert bool(posts) == (mode == "inference-failure")


# Layer: integration
def test_native_odr_missing_python_refuses_before_provider_discovery(tmp_path):
    with provider_server() as (endpoint, calls):
        result = native_sweep(tmp_path, endpoint, python_bin=tmp_path / "absent-python")
    assert result.returncode == 2 and not calls
    error = json.loads((tmp_path / "out/arbiter_error.json").read_text(encoding="utf-8"))
    assert error["phase"] == "preflight" and any(x.startswith("tool:") for x in error["failures"])
    assert not (tmp_path / "out/index.json").exists()


@pytest.mark.parametrize("damage", ["provider", "endpoint", "model", "missing-receipt", "empty-rounds", "invalid-round"])
# Layer: integration
def test_odr_retained_provider_evidence_refuses_conflicts(tmp_path, damage):
    with provider_server() as (endpoint, _calls):
        result = native_sweep(tmp_path, endpoint)
    assert result.returncode == 0, result.stdout + result.stderr
    artifact, = (tmp_path / "out").glob("odr_live_role_matrix.*.json")
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    case = payload["results"][0]["scenarios"][0]
    if damage == "endpoint":
        payload["config"]["provider_selection"]["base_url"] = "http://127.0.0.1:1"
    elif damage == "provider":
        case["rounds"][0]["architect_provider_raw"]["provider_name"] = "ollama"
    elif damage == "model":
        case["rounds"][0]["auditor_provider_raw"]["model"] = "unadmitted-model"
    elif damage == "missing-receipt":
        del case["rounds"][0]["architect_provider_raw"]
    else:
        case["rounds"] = [] if damage == "empty-rounds" else ["invalid"]
    artifact.write_text(json.dumps(payload), encoding="utf-8")
    before = artifact.read_bytes()
    arbiter = RunArbiter(plan_out=tmp_path / "unused-plan.json", error_out=tmp_path / "unused-error.json")
    with pytest.raises(ArbiterFailure, match="Shape validation failed"):
        arbiter.validate_run_output(path=artifact, architect_model=MODEL, auditor_model=MODEL,
            provider_selection=ProviderSelection("openai_compat", endpoint))
    assert artifact.read_bytes() == before


@pytest.mark.parametrize("mode", ["success", "inference-failure"])
# Layer: integration
def test_odr_pairing_closes_real_provider_clients(tmp_path, monkeypatch, mode):
    providers = []

    def record_provider(*args, **kwargs):
        provider = LocalModelProvider(*args, **kwargs)
        providers.append(provider)
        return provider

    monkeypatch.setattr(live_matrix, "LocalModelProvider", record_provider)
    monkeypatch.setenv("ORKET_LOCAL_PROMPTING_MODE", "shadow")
    monkeypatch.setenv("ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL", "false")
    monkeypatch.setenv("ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL", "false")
    scenario = live_matrix._load_scenario_inputs(live_matrix._load_scenarios()[0])
    with provider_server(mode=mode) as (endpoint, _calls):
        call = live_matrix._run_pairing(pairing=live_matrix.Pairing(MODEL, MODEL), scenario_inputs=[scenario],
            rounds=1, odr_cfg=live_matrix.ReactorConfig(), temperature=0.1, model_timeout=30,
            provider_selection=ProviderSelection("openai_compat", endpoint))
        if mode == "success":
            assert asyncio.run(call)["scenarios"]
        else:
            from orket.exceptions import ModelProviderError
            with pytest.raises(ModelProviderError):
                asyncio.run(call)
    assert len(providers) == 2 and all(provider.client.is_closed for provider in providers)


@pytest.mark.parametrize("invalid", ["credentials", "unknown-provider"])
# Layer: integration
def test_native_odr_invalid_provider_refuses_without_secret_output(tmp_path, invalid):
    endpoint = "http://test-user:do-not-print-this@127.0.0.1:1/v1" if invalid == "credentials" else "http://127.0.0.1:1/v1"
    result = native_sweep(tmp_path, endpoint, provider="unknown" if invalid == "unknown-provider" else "openai_compat")
    assert result.returncode == 2
    error_text = (tmp_path / "out/arbiter_error.json").read_text(encoding="utf-8")
    assert json.loads(error_text)["phase"] == "preflight"
    assert "do-not-print-this" not in error_text + result.stdout + result.stderr
    assert not (tmp_path / "out/arbiter_plan.json").exists()


@pytest.mark.parametrize("plan", [{"schema_version": "odr.run_arbiter.plan.v1"},
    {"schema_version": "odr.run_arbiter.plan.v2", "provider_selection": {"unexpected": "value"}}])
# Layer: contract
def test_unbound_odr_plan_refuses_before_discovery(tmp_path, plan):
    arbiter = RunArbiter(plan_out=tmp_path / "unused.json", error_out=tmp_path / "error.json")
    with pytest.raises(ArbiterFailure, match="provider admission is invalid"):
        arbiter.preflight(plan)


@pytest.mark.parametrize("spec_mode", ["missing", "invalid"])
# Layer: integration
def test_native_odr_base_spec_failure_has_preflight_artifact(tmp_path, spec_mode):
    with provider_server() as (endpoint, calls):
        result = native_sweep(tmp_path, endpoint, spec_mode=spec_mode)
    assert result.returncode == 2 and not calls, result.stderr
    error = json.loads((tmp_path / "out/arbiter_error.json").read_text(encoding="utf-8"))
    assert error["phase"] == "preflight" and not (tmp_path / "out/index.json").exists()


@pytest.mark.parametrize("arguments", [("--architect-models", ""), ("--auditor-models", ""),
    ("--leak-gate-mode", "invalid")])
# Layer: integration
def test_native_odr_invalid_sweep_inputs_refuse_before_discovery(tmp_path, arguments):
    with provider_server() as (endpoint, calls):
        result = native_sweep(tmp_path, endpoint, extra_args=arguments)
    assert result.returncode == 2 and not calls, result.stderr
    error = json.loads((tmp_path / "out/arbiter_error.json").read_text(encoding="utf-8"))
    assert error["phase"] == "preflight" and not (tmp_path / "out/arbiter_plan.json").exists()
