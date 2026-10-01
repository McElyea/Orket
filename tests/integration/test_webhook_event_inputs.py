"""Integration: actual webhook admission, native event writes and retained SQLite ordering."""
import asyncio

import httpx
import pytest

from orket.adapters.observability.logging_context import bind_logging, prepare_logging, selected_logging
from orket.application.services import gitea_webhook_runtime
from orket.core.contracts.log_event_inputs import LOG_EVENT_INPUT_ERROR
from orket.core.contracts.logging_inputs import LoggingInputs
from tests.helpers.webhook import application, signed
from tests.helpers.webhook_event_inputs import (
    admitted,
    assert_record,
    assert_settled,
    database_snapshot,
    hold_event,
    interrupt,
    records,
    refused_values,
    release,
    review_payload,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("stop", ["none", "cancel"])
async def test_asgi_signature_refusal_retains_invocation_event_values_and_root(tmp_path, monkeypatch, stop):
    monkeypatch.chdir(tmp_path)
    app = application(tmp_path, ORKET_TIMEZONE="MST")
    caller = await prepare_logging(LoggingInputs(tmp_path / "caller"))
    with bind_logging(caller):
        async with app.router.lifespan_context(app):
            runtime = app.state.webhook_runtime
            state = hold_event(monkeypatch, runtime, "webhook")
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                request = asyncio.create_task(client.post("/webhook/gitea", json={}))
                try:
                    await admitted(state, runtime, request)
                    assert (await client.get("/health")).status_code == 200
                    assert await database_snapshot(runtime.db.db_path) is None
                    state.payload["message"] = "late mutation"
                    state.payload["late"] = {"nested": ["value"]}
                    runtime.workspace = tmp_path / "late"
                    await interrupt(request, stop)
                finally:
                    outcome = await release(state, request)
                assert_settled(state, runtime)
                if stop == "cancel":
                    assert isinstance(outcome, asyncio.CancelledError)
                else:
                    assert outcome.status_code == 401 and outcome.json() == {"detail": "Missing signature"}
                assert await database_snapshot(runtime.db.db_path) is None
            assert selected_logging() is caller
        assert runtime.closed and runtime.client.is_closed
    await assert_record(tmp_path, "webhook", state.expected)
    assert not await records(tmp_path / "late/orket.log")


@pytest.mark.parametrize("stop", ["none", "cancel"])
async def test_public_review_event_preserves_dedupe_then_publication_then_cycle_order(tmp_path, monkeypatch, stop):
    monkeypatch.chdir(tmp_path)
    app = application(tmp_path, ORKET_TIMEZONE="MST")
    before = selected_logging(required=False)
    async with app.router.lifespan_context(app):
        runtime = app.state.webhook_runtime
        state = hold_event(monkeypatch, runtime, "pr_review")
        request = asyncio.create_task(runtime.handle_webhook("pull_request_review", review_payload()))
        try:
            await admitted(state, runtime, request)
            assert await database_snapshot(runtime.db.db_path) == {
                "delivery": [("capture-delivery",)], "cycles": [], "failures": []}
            state.payload["reviewer"] = "late reviewer"
            runtime.workspace = tmp_path / "late"
            await interrupt(request, stop)
        finally:
            outcome = await release(state, request)
        assert_settled(state, runtime)
        assert selected_logging(required=False) is before
        snapshot = await database_snapshot(runtime.db.db_path)
        assert snapshot["delivery"] == [("capture-delivery",)]
        if stop == "cancel":
            assert isinstance(outcome, asyncio.CancelledError)
            assert snapshot["cycles"] == snapshot["failures"] == []
        else:
            assert outcome["status"] == "changes_requested"
            assert snapshot["cycles"] == [(1,)] and snapshot["failures"] == [("reviewer", "Fix validation")]
        await assert_record(tmp_path, "pr_review", state.expected)
        assert not await records(tmp_path / "late/orket.log")
        # The next event selects its current phase root, rather than freezing construction state.
        await runtime.run_request(lambda: runtime._log_event("next_phase", {"phase": "later"}))
        await assert_record(tmp_path / "late", "next_phase", {"phase": "later"})
    assert runtime.closed and runtime.client.is_closed and runtime.active_request_count == 0


@pytest.mark.parametrize("stop", ["none", "cancel"])
async def test_admitted_nested_event_detaches_graph_before_native_entry(tmp_path, monkeypatch, stop):
    """Direct event-boundary guard through actual request admission; no dispatch claim."""
    monkeypatch.chdir(tmp_path)
    app = application(tmp_path, ORKET_TIMEZONE="MST")
    payload = {"nested": {"items": ["admitted"]}}
    async with app.router.lifespan_context(app):
        runtime = app.state.webhook_runtime
        state = hold_event(monkeypatch, runtime, "nested")
        request = asyncio.create_task(runtime.run_request(lambda: runtime._log_event("nested", payload)))
        try:
            await admitted(state, runtime, request)
            payload["nested"]["items"].append("late")
            runtime.workspace = tmp_path / "late"
            await interrupt(request, stop)
        finally:
            outcome = await release(state, request)
        assert_settled(state, runtime)
        assert isinstance(outcome, asyncio.CancelledError) if stop == "cancel" else outcome is None
        assert await database_snapshot(runtime.db.db_path) is None
    assert runtime.closed and runtime.client.is_closed
    await assert_record(tmp_path, "nested", {"nested": {"items": ["admitted"]}})
    assert not await records(tmp_path / "late/orket.log")


@pytest.mark.parametrize("kind", ["name", "container", "value", "cycle"])
async def test_unsupported_event_inputs_refuse_before_native_admission(tmp_path, monkeypatch, kind):
    """Direct event-boundary guard; native admission remains the real shared owner."""
    monkeypatch.chdir(tmp_path)
    app = application(tmp_path)
    calls = []
    async with app.router.lifespan_context(app):
        runtime = app.state.webhook_runtime
        actual_owner = gitea_webhook_runtime.run_owned_thread

        async def observe(operation, *, label):
            calls.append(label)
            return await actual_owner(operation, label=label)

        monkeypatch.setattr(gitea_webhook_runtime, "run_owned_thread", observe)
        name, payload, hook = refused_values(kind)
        before = selected_logging(required=False)
        with pytest.raises(TypeError, match=LOG_EVENT_INPUT_ERROR):
            await runtime.run_request(lambda: runtime._log_event(name, payload))
        assert selected_logging(required=False) is before
        assert hook.calls == 0 and "webhook-event-publication" not in calls
        assert runtime.active_request_count == 0
    assert runtime.closed and runtime.client.is_closed
    assert not await records(tmp_path / "orket.log")


@pytest.mark.parametrize("stop", ["none", "cancel"])
async def test_real_log_path_failure_keeps_native_identity_and_prior_dedupe(tmp_path, monkeypatch, stop):
    monkeypatch.chdir(tmp_path)
    app = application(tmp_path)
    await asyncio.to_thread((tmp_path / "orket.log").mkdir)
    async with app.router.lifespan_context(app):
        runtime = app.state.webhook_runtime
        state = hold_event(monkeypatch, runtime, "pr_review")
        request = asyncio.create_task(runtime.handle_webhook("pull_request_review", review_payload()))
        try:
            await admitted(state, runtime, request)
            assert await database_snapshot(runtime.db.db_path) == {
                "delivery": [("capture-delivery",)], "cycles": [], "failures": []}
            await interrupt(request, stop)
        finally:
            outcome = await release(state, request)
        assert_settled(state, runtime)
        assert isinstance(outcome, OSError) and outcome is state.native_error
        assert await database_snapshot(runtime.db.db_path) == {
            "delivery": [("capture-delivery",)], "cycles": [], "failures": []}
    assert runtime.closed and runtime.client.is_closed
    assert await asyncio.to_thread((tmp_path / "orket.log").is_dir)


async def test_asgi_nonfinite_event_projection_refuses_before_dispatch_and_native_log(tmp_path, monkeypatch):
    """A signed wire payload reaches real projection; required capture failure returns 500."""
    monkeypatch.chdir(tmp_path)
    app = application(tmp_path)
    calls = []
    async with app.router.lifespan_context(app):
        runtime = app.state.webhook_runtime
        actual_owner = gitea_webhook_runtime.run_owned_thread

        async def observe(operation, *, label):
            calls.append(label)
            return await actual_owner(operation, label=label)

        monkeypatch.setattr(gitea_webhook_runtime, "run_owned_thread", observe)
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            result = await signed(client, {"repository": {"full_name": float("nan")}})
        assert result.status_code == 500
        assert "webhook-event-publication" not in calls and runtime.active_request_count == 0
        assert await database_snapshot(runtime.db.db_path) is None
    assert runtime.closed and runtime.client.is_closed
    assert not await records(tmp_path / "orket.log")
