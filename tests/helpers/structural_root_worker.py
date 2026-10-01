"""Real board snapshots, replacements and adoption records under isolated root changes."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

from orket.adapters.storage import structural_board_store as stores
from orket.application.services import structural_reconciliation_service as reconciliation
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.core.domain.reconciler import StructuralReconciler as Policy
from orket.logging import bind_logging, prepare_logging
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.helpers.application_root_controls import (
    NativeHold,
    admitted,
    contents,
    origins,
    prepare_trees,
    records,
    settle,
)
from tests.helpers.core_effect_fixtures import BOARD_ASSETS
from tests.helpers.runtime_verification_hold import sqlite_response
from tests.helpers.sdk_observation_controls import public_caller


def install_native_observation(monkeypatch, hold, stage, state):
    snapshot, apply = stores.StructuralBoardStore._snapshot_sync, stores.StructuralBoardStore._apply_sync
    model, workspace = reconciliation.default_model_root, reconciliation.default_workspace_root

    def snap(owner, *args):
        if stage in {"snapshot", "constructor"}:
            hold.wait()
        try:
            result = snapshot(owner, *args)
            state["assets"] = result
            return result
        finally:
            if stage in {"snapshot", "constructor"}:
                hold.finished.set()

    def write(owner, *args):
        state["write_calls"] += 1
        selected = state["write_calls"] == (2 if stage == "second-apply" else 1)
        if stage in {"apply", "second-apply"} and selected:
            hold.wait()
        try:
            return apply(owner, *args)
        except BaseException as failure:
            state["failure"] = failure
            raise
        finally:
            if stage in {"apply", "second-apply"} and selected:
                hold.finished.set()

    def root(base=None):
        if stage == "default-before":
            hold.wait()
        result = model(base)
        state["defaults"].append(("model", str(result)))
        if stage == "default-after":
            hold.wait()
        hold.finished.set()
        return result

    def logging_root(base=None):
        result = workspace(base)
        state["defaults"].append(("workspace", str(result)))
        return result

    monkeypatch.setattr(stores.StructuralBoardStore, "_snapshot_sync", snap)
    monkeypatch.setattr(stores.StructuralBoardStore, "_apply_sync", write)
    monkeypatch.setattr(reconciliation, "default_model_root", root)
    monkeypatch.setattr(reconciliation, "default_workspace_root", logging_root)


async def arrange(first, other, route, stage):
    if route == "default":
        owner = reconciliation.StructuralReconciler()
        return owner, owner.reconcile()
    if route == "reconcile":
        owner = reconciliation.StructuralReconciler(Path("model"), Path("workspace/default"))
        return owner, owner.reconcile()
    owner = stores.StructuralBoardStore(Path("model"))
    if stage == "snapshot":
        await asyncio.to_thread((other / "model/product/issues/other-only.json").write_text,
                                '{"id":"other-only", "summary":"Other project"}', encoding="utf-8")
        return owner, owner.snapshot()
    if stage == "constructor":
        await asyncio.to_thread(os.chdir, other)

        async def run():
            plan = Policy.plan(await owner.snapshot())
            for update in plan.writes:
                await owner.apply(update)
            return plan
        return owner, run()
    plan = Policy.plan(await owner.snapshot())
    return owner, owner.apply(plan.writes[0])


async def perturb(first, other, owner, active, stage, change, plan):
    if change == "attribute":
        if isinstance(owner, stores.StructuralBoardStore):
            owner.root = other / "model"
        else:
            owner.root_path, owner.workspace = other / "model", other / "workspace/default"
    elif stage != "constructor":
        await asyncio.to_thread(os.chdir, other)
    if change == "drift":
        await asyncio.to_thread((first / "model" / plan.writes[1].relative_path).write_text,
                                '{"operator": true}', encoding="utf-8")
    if change == "cancel":
        active.cancel("first reconciliation interruption")
        await asyncio.sleep(0)
        active.cancel("later reconciliation interruption")


def assert_effects(first, other, route, stage, change, plan, state, result):
    original = {asset.relative_path: asset.content for asset in BOARD_ASSETS}
    left, right = contents(first), contents(other)
    first_records, other_records = records(first), records(other)
    expected = dict(original)
    count = 0 if stage == "snapshot" and route == "store" else 1 if route == "store" and stage == "apply" else 2
    if change == "drift":
        count = 1
        expected[plan.writes[1].relative_path] = '{"operator": true}'
    for update in plan.writes[:count]:
        expected[update.relative_path] = update.content
    if change == "drift":
        assert result is state["failure"] and type(result) is ValueError and "changed after snapshot" in str(result)
    elif change == "cancel":
        assert type(result) is asyncio.CancelledError and result.args == ("first reconciliation interruption",)
    elif route == "store" and stage == "snapshot":
        assert result == BOARD_ASSETS
    elif route == "store" and stage == "apply":
        assert result is None
    else:
        assert result == plan
    assert left == expected and right == original, "an admitted operation adopted the later project root"
    expected_events = [] if route == "store" else ["reconciler_start", "reconciler_orphan_epic_adopted", "reconciler_orphan_issue_adopted"][:count + 1]
    assert [record["event"] for record in first_records] == expected_events and not other_records
    if route != "store":
        assert first_records[0]["data"]["root_path"] == str(first / "model")
    if route == "default":
        assert state["defaults"] == [("model", str(first / "model")), ("workspace", str(first / "workspace/default"))]
    return {"selected_tree_exact": True, "other_tree_unchanged": True, "effect_count": count,
            "first_events": expected_events, "other_events": [], "partial_publication": change == "drift"}


async def observe(root, first, other, route, stage, change, monkeypatch):
    hold, state = NativeHold(), {"write_calls": 0, "defaults": []}
    install_native_observation(monkeypatch, hold, stage, state)
    owner, operation = await arrange(first, other, route, stage)
    plan = Policy.plan(BOARD_ASSETS)
    active = asyncio.create_task(public_caller(operation))
    try:
        await admitted(hold, active)
        await perturb(first, other, owner, active, stage, change, plan)
        assert await sqlite_response(root / "responsive.sqlite3", lambda *args: None) < .5
        assert not active.done() and not hold.finished.is_set()
        await asyncio.to_thread(write_payload_with_diff_ledger, root / "structural-before-release.json", {
            "route": route, "stage": stage, "change": change, "caller_pending": not active.done(),
            "first": await asyncio.to_thread(contents, first), "other": await asyncio.to_thread(contents, other)})
        hold.release.set()
        result = await asyncio.wait_for(active, 10)
        await settle(active, hold)
        await asyncio.to_thread(write_payload_with_diff_ledger, root / "structural-after-settlement.json", {
            "route": route, "stage": stage, "change": change, "result_type": type(result).__name__,
            "first": await asyncio.to_thread(contents, first), "other": await asyncio.to_thread(contents, other),
            "first_events": await asyncio.to_thread(records, first), "other_events": await asyncio.to_thread(records, other)})
        proof = await asyncio.to_thread(assert_effects, first, other, route, stage, change, plan, state, result)
        assert hold.calls == 1 and hold.finished.is_set() and not hold.expired
        return {**proof, "native_settled": True, "path": "primary", "result": "success"}
    finally:
        await settle(active, hold)


async def input_guard(first):
    with pytest.raises(ValueError, match="DRIVE_RELATIVE_ROOT_UNSUPPORTED"):
        stores.StructuralBoardStore(Path("C:relative"))
    with pytest.raises(ValueError, match="DRIVE_RELATIVE_ROOT_UNSUPPORTED"):
        await reconciliation.StructuralReconciler(Path("C:relative"), first / "workspace/default").reconcile()
    assert not await asyncio.to_thread(records, first)
    assert await asyncio.to_thread(contents, first) == {asset.relative_path: asset.content for asset in BOARD_ASSETS}
    return {"input_refused": True, "path": "primary", "result": "success"}


async def exercise(root, route, stage, change):
    first, other = await asyncio.to_thread(prepare_trees, root)
    prepared = await prepare_logging(LoggingInputs(root, timezone_name="MST"))
    with pytest.MonkeyPatch.context() as monkeypatch, bind_logging(prepared):
        monkeypatch.chdir(first)
        result = await input_guard(first) if route == "input" else await observe(root, first, other, route, stage, change, monkeypatch)
    return {**result, "route": route, "stage": stage, "change": change}


def main():
    root = Path(sys.argv[1]).resolve()
    result = asyncio.run(exercise(root, *sys.argv[2:]))
    write_payload_with_diff_ledger(root / "result.json", {**result, **origins({"service": reconciliation, "store": stores})})


if __name__ == "__main__":
    main()
