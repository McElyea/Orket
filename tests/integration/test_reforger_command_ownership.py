"""Layer: integration. Real tool compilation keeps its worker and output scope owned."""
import asyncio
import json
import threading

import pytest

from orket.application.services.reforger_service import ReforgerService
from orket.application.services.toolbox import ToolBox
from orket.reforger.routes import TextMysteryPersonaRouteV0
from tests.integration.test_reforger_tools_family import _seed_textmystery_inputs

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
RESPONSIVENESS_SECONDS = 0.5
SETTLEMENT_SECONDS = 3


@pytest.mark.parametrize("stop", ["cancel", "timeout"])
@pytest.mark.parametrize("entrypoint", ["toolbox", "service"])
async def test_reforger_tool_retains_worker_after_interruption(tmp_path, monkeypatch, stop, entrypoint):
    workspace = tmp_path / "workspace"
    await asyncio.to_thread(workspace.mkdir)
    await asyncio.to_thread(_seed_textmystery_inputs, tmp_path)
    tools = ToolBox(None, str(workspace), [str(tmp_path)])
    entered, release, settled = threading.Event(), threading.Event(), threading.Event()
    original = TextMysteryPersonaRouteV0.inspect

    def held(route, root):
        plan = original(route, root)
        entered.set()
        try:
            assert release.wait(15), "Fixture inspection was not released"
            return plan
        finally:
            settled.set()

    monkeypatch.setattr(TextMysteryPersonaRouteV0, "inspect", held)
    args = {
        "route_id": "textmystery_v1", "input_dir": str(tmp_path), "mode": "truth_only",
    }
    if entrypoint == "toolbox":
        operation = tools.execute("reforger_inspect", args,
                                  context={"tool_timeout_seconds": 0.05 if stop == "timeout" else 20})
    else:
        operation = ReforgerService(workspace, (tmp_path,)).inspect(args)
        if stop == "timeout":
            operation = asyncio.wait_for(operation, 0.05)
    request = asyncio.create_task(operation)
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        await asyncio.wait_for(asyncio.sleep(0), RESPONSIVENESS_SECONDS)
        if stop == "cancel":
            request.cancel()
            await asyncio.sleep(0)
            request.cancel()
        await asyncio.sleep(0.15)
        assert not request.done(), "Tool call escaped while its compilation worker remained active"
        release.set()
        result, = await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), SETTLEMENT_SECONDS)
        assert settled.is_set()
        if stop == "cancel" or entrypoint == "service":
            assert isinstance(result, asyncio.CancelledError if stop == "cancel" else TimeoutError)
        else:
            assert result["error"] == "tool_timeout"
        reports = await asyncio.to_thread(lambda: list((workspace / "reforger" / "inspect").glob("*/route_plan.json")))
        assert len(reports) == 1
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), SETTLEMENT_SECONDS)
        assert await asyncio.to_thread(settled.wait, SETTLEMENT_SECONDS)


async def test_reforger_cannot_replace_the_workspace_root(tmp_path):
    workspace = tmp_path / "workspace"
    await asyncio.to_thread(workspace.mkdir)
    sentinel = workspace / "operator-state.txt"
    await asyncio.to_thread(sentinel.write_text, "retain", encoding="utf-8")
    await asyncio.to_thread(_seed_textmystery_inputs, tmp_path)
    tools = ToolBox(None, str(workspace), [str(tmp_path)])
    result = await tools.execute("reforger_run", {
        "route_id": "textmystery_v1", "input_dir": str(tmp_path), "output_dir": ".",
        "mode": "truth_only", "scenario_pack": "truth_only_v0", "seed": 1, "max_iters": 2,
        "model_id": "fake",
    })
    assert result["ok"] is False and result["code"] == "PATCH_OUT_OF_SURFACE"
    assert await asyncio.to_thread(sentinel.read_text, encoding="utf-8") == "retain"
    assert not await asyncio.to_thread((workspace / "reforger").exists)


async def test_driver_reforger_keeps_event_loop_responsive(tmp_path, monkeypatch):
    from tests.application.test_driver_cli import _build_driver

    driver = await asyncio.to_thread(_build_driver, tmp_path)
    await asyncio.to_thread(_seed_textmystery_inputs, tmp_path)
    entered, heartbeat, release = threading.Event(), threading.Event(), threading.Event()
    observed = []
    original = TextMysteryPersonaRouteV0.inspect
    loop = asyncio.get_running_loop()

    def held(route, root):
        entered.set()
        assert release.wait(5)
        return original(route, root)

    def watchdog():
        if entered.wait(3):
            loop.call_soon_threadsafe(heartbeat.set)
            observed.append(heartbeat.wait(RESPONSIVENESS_SECONDS))
        release.set()

    monkeypatch.setattr(TextMysteryPersonaRouteV0, "inspect", held)
    watcher = threading.Thread(target=watchdog)
    watcher.start()
    try:
        response = await driver.process_request(f'/reforge inspect --route textmystery_v1 --in "{tmp_path}"')
        assert "Reforger inspect ok" in response
        assert observed == [True], "Direct driver compiler blocked the event loop"
    finally:
        release.set()
        await asyncio.to_thread(watcher.join, 3)
        assert not watcher.is_alive()


@pytest.mark.parametrize("output", ["reforger", "reforger/run/nested", "source", "source/content",
                                    "source/reforge/scenario_packs"])
async def test_reforger_refuses_output_overlapping_inputs_or_artifacts(tmp_path, output):
    source = tmp_path / "source"
    await asyncio.to_thread(_seed_textmystery_inputs, source)
    sentinel = source / "content/prompts/npcs.yaml"
    before = await asyncio.to_thread(sentinel.read_bytes)
    result = await ReforgerService(tmp_path).run({
        "route_id": "textmystery_v1", "input_dir": "source", "output_dir": output,
        "mode": "truth_only", "scenario_pack": "truth_only_v0",
    })
    assert result["ok"] is False and result["code"] == "PATCH_OUT_OF_SURFACE"
    assert await asyncio.to_thread(sentinel.read_bytes) == before
    assert not await asyncio.to_thread((tmp_path / "reforger").exists)


async def test_reforger_input_digests_exclude_unrelated_project_and_prior_outputs(tmp_path):
    await asyncio.to_thread(_seed_textmystery_inputs, tmp_path)
    service = ReforgerService(tmp_path / "workspace", (tmp_path,))
    args = {"route_id": "textmystery_v1", "input_dir": str(tmp_path), "output_dir": "compiled",
            "mode": "truth_only", "seed": 1, "max_iters": 2}
    first = await service.run(args)
    from pathlib import Path

    artifact = Path(first["artifact_root"]) / "run/artifacts/bundle_digests.json"
    before = await asyncio.to_thread(artifact.read_bytes)
    await asyncio.to_thread((tmp_path / "unrelated.txt").write_text, "changed", encoding="utf-8")
    second = await service.run(args)
    assert first["ok"] is True and second["ok"] is True
    assert await asyncio.to_thread(artifact.read_bytes) == before
    manifest = await asyncio.to_thread((artifact.parent / "inputs_manifest.json").read_bytes)
    assert set(json.loads(manifest)) == set(TextMysteryPersonaRouteV0.expected_inputs)


async def test_reforger_does_not_claim_success_after_output_corruption(tmp_path, monkeypatch):
    from orket.adapters.storage import reforger_output

    await asyncio.to_thread(_seed_textmystery_inputs, tmp_path)
    workspace = tmp_path / "workspace"
    original = reforger_output.write_verified_bytes

    def corrupt(path, payload):
        original(path, payload)
        if path.is_relative_to(workspace / "compiled"):
            path.write_bytes(b"corrupted after file publication")

    monkeypatch.setattr(reforger_output, "write_verified_bytes", corrupt)
    with pytest.raises(OSError, match="REFORGER_OUTPUT_UNVERIFIED"):
        await ReforgerService(workspace, (tmp_path,)).run({
            "route_id": "textmystery_v1", "input_dir": str(tmp_path), "output_dir": "compiled",
            "mode": "truth_only", "seed": 1, "max_iters": 2,
        })
