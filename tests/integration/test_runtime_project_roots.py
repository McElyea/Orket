"""Real project discovery/effects with an isolated package-location fixture."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

import orket.discovery as discovery
import orket.project_paths as project_paths
from orket.driver import OrketDriver

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def stage_board(root, name):
    """Fixture filesystem setup; callers offload this synchronous helper."""
    stage_inputs(
        root,
        {
            "model/core/rocks/run_the_business.json": {"name": "Run the Business", "epics": []},
            f"model/core/epics/{name}.json": {"name": name, "issues": []},
        },
    )


def stage_inputs(root, inputs):
    """Shared fixture writer, used only through an owned test thread."""
    for relative, payload in inputs.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload), encoding="utf-8")


def read_board(root):
    """Fixture observation; callers offload the read."""
    return json.loads((root / "model/core/rocks/run_the_business.json").read_text(encoding="utf-8"))


# Layer: integration
async def test_discovery_and_reconciliation_share_each_invocation_project(tmp_path, monkeypatch):
    first, second, package = (tmp_path / name for name in ("first", "second", "site-packages"))
    for root, name in [(first, "first_epic"), (second, "second_epic"), (package, "package_decoy")]:
        await asyncio.to_thread(stage_board, root, name)
    # A wrong package-relative selection can only affect this disposable decoy.
    monkeypatch.setattr(project_paths, "__file__", str(package / "orket/project_paths.py"))
    for root, name in [(first, "first_epic"), (second, "second_epic")]:
        monkeypatch.chdir(root)
        assets = await asyncio.to_thread(discovery.discover_project_assets)
        outcome = await asyncio.to_thread(discovery.run_startup_reconciliation)
        assert assets["epics"] == [name]
        assert outcome == "success"
        assert (await asyncio.to_thread(read_board, root))["epics"] == [{"epic": name, "department": "core"}]
        assert await asyncio.to_thread(project_paths.default_project_root) == root
    assert (await asyncio.to_thread(read_board, package))["epics"] == []


@pytest.mark.parametrize("explicit", [False, True])
# Layer: integration
async def test_driver_keeps_selected_project_when_caller_directory_changes(tmp_path, monkeypatch, explicit):
    first, second, package = (tmp_path / name for name in ("first", "second", "site-packages"))
    for root in (first, second, package):
        await asyncio.to_thread(root.mkdir)
    monkeypatch.setattr(project_paths, "__file__", str(package / "orket/project_paths.py"))
    monkeypatch.chdir(second if explicit else first)
    driver = await asyncio.to_thread(
        OrketDriver,
        provider=SimpleNamespace(model="fixture"),
        project_root=first if explicit else None,
        strict_config=False,
    )
    monkeypatch.chdir(second)
    await driver.fs.write_file("retained.txt", "selected project")
    assert driver.project_root == first
    assert driver.model_root == first / "model"
    assert driver.workspace_root == first / "workspace/default"
    assert await asyncio.to_thread((first / "retained.txt").read_text, encoding="utf-8") == "selected project"
    assert not await asyncio.to_thread((second / "retained.txt").exists)
    assert not await asyncio.to_thread((package / "retained.txt").exists)


# Layer: integration
async def test_driver_reads_prompt_assets_from_explicit_project(tmp_path):
    await asyncio.to_thread(
        stage_inputs,
        tmp_path,
        {
            "model/core/skills/operations_lead.json": {
                "name": "Selected operator",
                "intent": "Inspect selected project",
                "responsibilities": ["Inspect"],
            },
            "model/core/dialects/generic.json": {
                "model_family": "generic",
                "dsl_format": "JSON",
                "constraints": ["JSON only"],
                "hallucination_guard": "Do not invent effects",
            },
        },
    )
    driver = await asyncio.to_thread(
        OrketDriver, provider=SimpleNamespace(model="fixture"), project_root=tmp_path, strict_config=True
    )
    assert driver.prompting_mode == "governed" and not driver.config_degraded
    assert driver.skill.name == "Selected operator" and driver.dialect.model_family == "generic"


# Layer: integration
async def test_missing_project_board_still_reports_reconciliation_failure(tmp_path, monkeypatch, caplog):
    package = tmp_path / "site-packages"
    await asyncio.to_thread(stage_board, package, "package_decoy")
    monkeypatch.setattr(project_paths, "__file__", str(package / "orket/project_paths.py"))
    monkeypatch.chdir(tmp_path)
    assert await asyncio.to_thread(discovery.run_startup_reconciliation) == "failed"
    assert not await asyncio.to_thread((tmp_path / "model").exists)
    assert (await asyncio.to_thread(read_board, package))["epics"] == []
    failures = [row.orket_record["data"] for row in caplog.records if row.message == "discovery_reconcile_failed"]
    assert failures and repr(str(tmp_path / "model")) in failures[-1]["error"]
