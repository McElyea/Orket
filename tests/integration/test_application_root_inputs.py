"""Integration: application invocation roots retain real selected-tree facts and effects."""
from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path

import pytest

from orket.adapters.storage import structural_board_store as stores
from orket.application.services import structural_reconciliation_service as reconciliation
from orket.application.services import tool_gate_service as gates
from tests.integration.test_logging_preparation_lifetime import run_worker

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
HELPERS = Path(__file__).resolve().parents[1] / "helpers"
GATE_CASES = [("governed", "cwd", "none"), ("governed", "attribute", "none"),
              ("facts", "cwd", "none"), ("facts", "attribute", "cancel"),
              ("facts", "cwd", "invalid-ast"), ("input", "escape", "none"), ("input", "drive", "none")]
STRUCTURAL_CASES = [("reconcile", "snapshot", "cwd"), ("reconcile", "apply", "cwd"),
    ("reconcile", "apply", "cancel"), ("reconcile", "second-apply", "drift"),
    ("default", "default-before", "cwd"), ("default", "default-after", "cwd"),
    ("default", "default-after", "attribute"), ("store", "constructor", "cwd"),
    ("store", "snapshot", "attribute"), ("store", "apply", "attribute"), ("input", "drive", "none")]


async def assert_sources(data, modules):
    expected = await asyncio.to_thread(lambda: {name: {"path": str(Path(module.__file__).resolve()),
        "sha256": hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()} for name, module in modules.items()})
    assert data["sources"] == expected


@pytest.mark.parametrize("route,change,stop", GATE_CASES)
async def test_gate_root_is_selected_before_native_validation(tmp_path, route, change, stop, record_property):
    if change == "drive" and os.name != "nt":
        pytest.skip("Windows drive-relative root semantics")
    data = await run_worker(tmp_path, HELPERS / "tool_gate_root_worker.py", [route, change, stop], record_property)
    assert (data["route"], data["change"], data["stop"]) == (route, change, stop)
    assert data["path"] == "primary" and data["result"] == "success"
    assert data["input_refused"] if route == "input" else data["selected_root"] and data["native_settled"]
    await assert_sources(data, {"gate": gates})


@pytest.mark.parametrize("route,stage,change", STRUCTURAL_CASES)
async def test_structural_roots_preserve_snapshot_write_and_adoption_tree(tmp_path, route, stage, change, record_property):
    if stage == "drive" and os.name != "nt":
        pytest.skip("Windows drive-relative root semantics")
    data = await run_worker(tmp_path, HELPERS / "structural_root_worker.py", [route, stage, change], record_property)
    assert (data["route"], data["stage"], data["change"]) == (route, stage, change)
    assert data["path"] == "primary" and data["result"] == "success"
    if route == "input":
        assert data["input_refused"]
    else:
        assert data["selected_tree_exact"] and data["other_tree_unchanged"] and data["native_settled"]
        assert data["partial_publication"] is (change == "drift")
    await assert_sources(data, {"service": reconciliation, "store": stores})
