"""Integration: support graphs retain native files without acquiring execution authority."""
import asyncio
import json
from pathlib import Path

import pytest

from orket.runtime.evidence import run_evidence_graph as graph
from orket.runtime.evidence import run_evidence_graph_rendering as rendering
from orket.runtime.evidence.run_evidence_graph_projection import project_run_evidence_graph_primary_lineage
from tests.helpers.runtime_verification_hold import hold_stream
from tests.integration.test_governed_demo_ownership import file_exists, observe_held
from tests.integration.test_marshaller_attempt_ownership import hold_native
from tests.integration.test_marshaller_publication_ownership import assert_outcome, roots
from tests.runtime.run_evidence_graph_test_support import GENERATED_AT, seed_complete_primary_lineage_sqlite

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def payload():
    return graph.build_blocked_run_evidence_graph_payload(run_id="original-run", generation_timestamp=GENERATED_AT,
        selected_views=["full_lineage"], issues=[{"code": "fixture_missing", "detail": "Support graph only"}])


@pytest.mark.parametrize("format,operation", [("json", "directory"), ("json", "write"), ("json", "close"),
                                              ("rendered", "directory"), ("rendered", "write"), ("rendered", "close")])
@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("failure", [False, True])
async def test_graph_native_publication_captures_payload(tmp_path, monkeypatch, format, operation, stop, failure, record_property):
    first, other = await roots(tmp_path)
    value = payload()
    parent = first / "runs/session"
    selected = parent / ("run_evidence_graph.json" if format == "json" else "run_evidence_graph.mmd")
    hold = (hold_native(monkeypatch, Path, "mkdir", lambda path, *args, **kwargs: path == parent, failure)
            if operation == "directory" else hold_stream(monkeypatch, selected, operation, failure=failure))
    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(5), deadline:
            if format == "json":
                return await graph.write_run_evidence_graph_artifact(root=first, session_id="session", payload=value)
            return await rendering.write_run_evidence_graph_rendered_artifacts(root=first, session_id="session", payload=value)

    task = asyncio.create_task(dispatch())
    try:
        assert await asyncio.to_thread(hold.entered.wait, 3)
        value["run_id"] = "late-run"
        value["issues"][0]["detail"] = "late-detail"
        result = await observe_held(task, deadline, hold, stop, other, monkeypatch, record_property)
        assert_outcome(result, stop, failure)
        if operation != "directory" or (stop == "none" and not failure):
            content = await asyncio.to_thread(selected.read_text, encoding="utf-8")
            assert "original-run" in content and "late-run" not in content
            if format == "json":
                assert json.loads(content)["projection_only"] is True
        html = parent / "run_evidence_graph.html"
        assert await file_exists(html) == (format == "rendered" and stop == "none" and not failure)
        if await file_exists(html):
            content = await asyncio.to_thread(html.read_text, encoding="utf-8")
            assert "original-run" in content and "late-run" not in content and "late-detail" not in content
        assert not await file_exists(other / "runs")
        assert all(stream.closed for stream in getattr(hold, "streams", []))
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


@pytest.mark.parametrize("phase", ["root", "summary-read", "summary-close"])
@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("failure", [False, True])
async def test_graph_projection_owns_real_lineage_observations(tmp_path, monkeypatch, phase, stop, failure, record_property):
    first, other = await roots(tmp_path)
    executions, records, _, session, run = await seed_complete_primary_lineage_sqlite(tmp_path=first)
    run_before = await executions.get_run_record(run_id=run)
    root = first / "runs" / session
    summary = root / "run_summary.json"
    before = await asyncio.to_thread(summary.read_bytes)
    hold = (hold_native(monkeypatch, Path, "exists", lambda path: path == root, failure) if phase == "root" else
            hold_stream(monkeypatch, summary, "read" if phase == "summary-read" else "close", failure=failure))
    views = ["full_lineage"]
    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(10), deadline:
            return await project_run_evidence_graph_primary_lineage(root=first, session_id=session, run_id=run,
                generation_timestamp=GENERATED_AT, execution_repository=executions,
                record_repository=records, selected_views=views)

    task = asyncio.create_task(dispatch())
    try:
        assert await asyncio.to_thread(hold.entered.wait, 3)
        views.append("closure_path")
        result = await observe_held(task, deadline, hold, stop, other, monkeypatch, record_property)
        if failure and phase != "root":
            assert result["graph_result"] == "degraded" and result["projection_only"] is True
            assert any(issue["code"] == "supplemental_run_summary_invalid" for issue in result["issues"])
        else:
            assert_outcome(result, stop, failure)
        if not isinstance(result, BaseException):
            assert result["selected_views"] == ["full_lineage"] and result["projection_only"] is True
        assert await executions.get_run_record(run_id=run) == run_before
        assert await asyncio.to_thread(summary.read_bytes) == before
        assert all(stream.closed for stream in getattr(hold, "streams", []))
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


@pytest.mark.parametrize("format", ["json", "rendered"])
async def test_graph_relative_publication_root_is_bound(tmp_path, monkeypatch, format, record_property):
    first, other = await roots(tmp_path)
    monkeypatch.chdir(first)
    hold = hold_native(monkeypatch, Path, "mkdir", lambda path, *args, **kwargs: path.name == "session", False)
    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(5), deadline:
            if format == "json":
                return await graph.write_run_evidence_graph_artifact(root=Path(), session_id="session", payload=payload())
            return await rendering.write_run_evidence_graph_rendered_artifacts(root=Path(), session_id="session", payload=payload())

    task = asyncio.create_task(dispatch())
    try:
        result = await observe_held(task, deadline, hold, "none", other, monkeypatch, record_property)
        assert not isinstance(result, BaseException), repr(result)
        assert await file_exists(first / "runs/session")
        assert not await file_exists(other / "runs")
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
