"""Application model preparation with real files and owned, controlled workers."""
import asyncio
import hashlib
import json
import threading
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from orket.application.services import model_selection_service as module
from orket.core.contracts.model_selection import ModelSelectionInput
from orket.decision_nodes.builtins import DefaultPromptStrategyNode

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# Layer: integration
@pytest.mark.parametrize("source", ["environment", "preferences", "organization"])
async def test_prepared_selection_cannot_follow_later_caller_mutation(monkeypatch, source):
    environment, preferences, rules = {}, {"models": {}}, {"models": {}}
    if source == "environment":
        environment["ORKET_MODEL_CODER"] = "captured"
    elif source == "preferences":
        preferences["models"]["coder"] = "captured"
    else:
        rules["models"]["coder"] = "captured"
    owner = module.ModelSelectionService(environment=environment)
    prepared = await owner.prepare(SimpleNamespace(process_rules=rules), preferences, {})
    first = prepared.select("coder")
    environment["ORKET_MODEL_CODER"] = "later"
    monkeypatch.setenv("ORKET_MODEL_CODER", "later")
    preferences["models"]["coder"] = "later"
    rules["models"]["coder"] = "later"
    second = prepared.select("coder")
    assert first.final_model == second.final_model == "captured"
    assert first == second and first is not second


# Layer: integration
@pytest.mark.parametrize("cancel", [False, True])
async def test_real_score_read_captures_inputs_and_retains_worker(tmp_path, monkeypatch, cancel):
    path = tmp_path / "scores.json"
    raw = json.dumps({"model_compliance": {"candidate": {"compliance_score": 10}}}).encode()
    await asyncio.to_thread(path.write_bytes, raw)
    environment = {"ORKET_MODEL_CODER": "candidate"}
    policy = {"min_score": 85, "fallback_model": "captured-fallback", "score_source": str(path)}
    settings = {"model_compliance_policy": policy}
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    worker_threads = []
    actual = module.read_model_scores

    def held_read(name):
        result = actual(name)
        worker_threads.append(threading.get_ident())
        started.set()
        assert release.wait(10)
        finished.set()
        return result

    monkeypatch.setattr(module, "read_model_scores", held_read)
    owner = module.ModelSelectionService(environment=environment)
    task = asyncio.create_task(owner.prepare(preferences={}, user_settings=settings))
    try:
        assert await asyncio.to_thread(started.wait, 3)
        assert worker_threads == [worker_threads[0]] and worker_threads[0] != threading.get_ident()
        environment["ORKET_MODEL_CODER"] = "later"
        policy["fallback_model"] = "later-fallback"
        await asyncio.to_thread(path.write_text, "{}")
        if cancel:
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.wait_for(asyncio.sleep(0.02), 0.5)
        assert not task.done() and not finished.is_set()
    finally:
        release.set()
        if cancel:
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            prepared = await task
    assert finished.is_set()
    if not cancel:
        result = prepared.select("coder")
        assert result.final_model == "captured-fallback" and result.reason == "score_below_threshold"
        assert result.score_source.sha256 == hashlib.sha256(raw).hexdigest()
        assert result.score_source.status == "observed"


# Layer: integration
@pytest.mark.parametrize("contents,status", [(None, "missing"), ("not-json", "invalid"), ("{}", "invalid")])
async def test_unobserved_score_report_is_disclosed(tmp_path, caplog, contents, status):
    path = tmp_path / "scores.json"
    if contents is not None:
        await asyncio.to_thread(path.write_text, contents)
    policy = {"min_score": 85, "fallback_model": "fallback", "score_source": str(path),
              "model_scores": {"candidate": 10}}
    prepared = await module.ModelSelectionService(environment={}).prepare(
        preferences={"models": {"coder": "candidate"}}, user_settings={"model_compliance_policy": policy})
    result = prepared.select("coder")
    assert result.final_model == "fallback" and result.score == 10
    assert result.score_source.status == status and result.score_source.error
    assert result.to_payload()["score_source"]["status"] == status
    assert "Model selection score report" in caplog.text


# Layer: integration
async def test_score_report_is_reobserved_by_new_preparation(tmp_path):
    path = tmp_path / "scores.json"
    policy = {"min_score": 85, "fallback_model": "fallback", "score_source": str(path)}
    owner = module.ModelSelectionService(environment={"ORKET_MODEL_CODER": "candidate"})
    await asyncio.to_thread(path.write_text, json.dumps({"model_compliance": {"candidate": {"compliance_score": 90}}}))
    first = await owner.prepare(preferences={}, user_settings={"model_compliance_policy": policy})
    await asyncio.to_thread(path.write_text, json.dumps({"model_compliance": {"candidate": {"compliance_score": 10}}}))
    second = await owner.prepare(preferences={}, user_settings={"model_compliance_policy": policy})
    assert first.select("coder").final_model == "candidate"
    assert second.select("coder").final_model == "fallback"
    assert first.inputs.compliance.observation.sha256 != second.inputs.compliance.observation.sha256


# Layer: integration
async def test_partial_score_report_rejects_nonfinite_rows_and_retains_valid_scores(tmp_path, caplog):
    path = tmp_path / "scores.json"
    await asyncio.to_thread(path.write_text, json.dumps({"model_compliance": {
        "candidate": {"compliance_score": float("nan")}, "other": {"compliance_score": 10}}}))
    prepared = await module.ModelSelectionService(environment={}).prepare(
        preferences={"models": {"coder": "candidate", "reviewer": "other"}}, user_settings={
            "model_compliance_policy": {"min_score": 85, "score_source": str(path), "fallback_model": "fallback"}})
    first, second = prepared.select("coder"), prepared.select("reviewer")
    assert first.reason == "score_missing" and first.final_model == "candidate"
    assert second.reason == "score_below_threshold" and second.final_model == "fallback"
    assert first.score_source.status == second.score_source.status == "partial"
    assert "1 invalid score rows" in caplog.text


# Layer: integration
async def test_unreadable_report_is_explicit_and_override_retains_priority(tmp_path):
    prepared = await module.ModelSelectionService(environment={}).prepare(
        preferences={}, user_settings={"model_compliance_policy": {
            "min_score": 85, "score_source": str(tmp_path), "blocked_models": ["operator"]}})
    selected = prepared.select("coder", override="operator")
    assert selected.reason == "override" and selected.final_model == "operator" and not selected.demoted
    assert selected.score_source.status == "unavailable" and selected.score_source.error


# Layer: integration
async def test_builtin_prompt_node_accepts_values_without_selector_callback(tmp_path):
    marker = tmp_path / "effect.txt"

    class Callback:
        def select(self, **kwargs):
            marker.write_text("unexpected")
            return "candidate"

    with pytest.raises(TypeError):
        DefaultPromptStrategyNode(Callback())
    request = ModelSelectionInput(role="coder", preferred_model="candidate")
    with pytest.raises(FrozenInstanceError):
        request.preferred_model = "later"
    assert DefaultPromptStrategyNode().select_model(request) == "candidate"
    assert not marker.exists()
