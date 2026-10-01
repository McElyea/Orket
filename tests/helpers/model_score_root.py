"""Native holds delegate the actual model-settings/score operation after release."""
import asyncio
import hashlib
import json
import threading
from types import SimpleNamespace

from orket.application.services import model_selection_service as module


def score_bytes(score):
    return json.dumps({"model_compliance": {"candidate": {"compliance_score": score}}}).encode()


def seed_roots(tmp_path, contents="observed"):
    original, later = tmp_path / "original", tmp_path / "later"
    original.mkdir()
    later.mkdir()
    raw = {"observed": score_bytes(10), "invalid": b"not-json", "partial": json.dumps({
        "model_compliance": {"candidate": {"compliance_score": 10}, "invalid": {"compliance_score": "bad"}}}).encode()}
    if contents == "unavailable":
        (original / "scores.json").mkdir()
    elif contents != "missing":
        (original / "scores.json").write_bytes(raw[contents])
    (later / "scores.json").write_bytes(score_bytes(99))
    return original, later, raw.get(contents)


def score_settings(source):
    return {"model_compliance_policy": {"min_score": 85, "fallback_model": "policy-fallback",
        "score_source": str(source), "model_scores": {"candidate": 5}}}


def hold_preparation(monkeypatch, label):
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
                            thread=None, labels=[], score_calls=[], observations=[])
    owned, read = module.run_owned_thread, module.read_model_scores

    def record_score(path):
        state.score_calls.append(path)
        value = read(path)
        state.observations.append(value)
        return value

    async def held(operation, *, label):
        state.labels.append(label)
        if label != state.label:
            return await owned(operation, label=label)

        def native():
            state.thread = threading.get_ident()
            state.entered.set()
            try:
                assert state.release.wait(10), "model preparation hold was not released"
                return operation()
            finally:
                state.finished.set()

        return await owned(native, label=label)

    state.label = label
    monkeypatch.setattr(module, "read_model_scores", record_score)
    monkeypatch.setattr(module, "run_owned_thread", held)
    return state


async def entered(hold):
    assert await asyncio.to_thread(hold.entered.wait, 3), "native preparation did not enter"
    assert hold.thread != threading.get_ident()
    assert not hold.finished.is_set()


async def settle(task, hold):
    hold.release.set()
    await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 10)
    if hold.entered.is_set():
        assert hold.finished.is_set()


def assert_observation(observation, original, raw, status="observed"):
    assert observation.path == str(original / "scores.json")
    assert observation.status == status
    assert observation.sha256 == (hashlib.sha256(raw).hexdigest() if raw is not None else "")
    if status != "observed":
        assert observation.error


def assert_selection(prepared, original, raw, status="observed"):
    decision = prepared.select("coder")
    assert decision.selected_model == "candidate"
    assert decision.final_model == "policy-fallback" and decision.demoted
    assert decision.reason == "score_below_threshold"
    assert decision.score == (10 if status in {"observed", "partial"} else 5)
    assert_observation(decision.score_source, original, raw, status)
    override = prepared.select("coder", override="operator")
    assert override.final_model == "operator" and override.reason == "override" and not override.demoted
    assert override.score_source == decision.score_source
