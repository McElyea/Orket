"""Layer: integration. Actual LSI effects, input capture and no-op preservation."""

import asyncio
import json
from pathlib import Path

import pytest

from orket.kernel.v1.state.lsi import LocalSovereignIndex
from orket.kernel.v1.state.promotion import REPAIR_ACKNOWLEDGEMENT, promote_turn, repair_run_ledger

pytestmark = pytest.mark.integration


def stage(index, *, turn="turn-0001"):
    return index.stage_triplet(
        run_id="run-state",
        turn_id=turn,
        stem="data/item",
        body={"dto_type": "item", "id": "item:one"},
        links={"target": {"type": "item", "id": "item:one"}},
        manifest={},
    )


def tree(root, *, exclude_ledger=False):
    return {
        path.relative_to(root).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file() and not (exclude_ledger and path.name == "run_ledger.json")
    }


def test_direct_lsi_retains_its_initial_lexical_root(tmp_path, monkeypatch):
    first, later = tmp_path / "first", tmp_path / "later"
    first.mkdir()
    later.mkdir()
    monkeypatch.chdir(first)
    index = LocalSovereignIndex("state")
    monkeypatch.chdir(later)
    stage(index)
    assert list((first / "state").rglob("item.json"))
    assert not (later / "state").exists()
    assert Path(index.root) == first / "state"


def test_stage_captures_all_triplet_values_before_the_first_write(tmp_path, monkeypatch):
    index = LocalSovereignIndex(str(tmp_path))
    body = {"dto_type": "item", "id": "item:one"}
    links = {"target": {"type": "item", "id": "item:one"}}
    write = Path.write_bytes
    written = []

    def mutate_after_write(path, data):
        result = write(path, data)
        written.append(path)
        body.update(dto_type="changed", id="changed:one")
        links["target"].update(type="changed", id="changed:one")
        return result

    monkeypatch.setattr(Path, "write_bytes", mutate_after_write)
    digests = index.stage_triplet(
        run_id="run-state",
        turn_id="turn-0001",
        stem="data/item",
        body=body,
        links=links,
        manifest={},
    )
    assert written and digests.dto_type == "item"
    record = index.read_triplet_record(scope="staging", stem="data/item", run_id="run-state", turn_id="turn-0001")
    assert record["dto_type"] == "item"
    assert index.read_refs_sources(
        scope="staging", ref_type="item", ref_id="item:one", run_id="run-state", turn_id="turn-0001"
    )
    assert not index.read_refs_sources(
        scope="staging", ref_type="changed", ref_id="changed:one", run_id="run-state", turn_id="turn-0001"
    )
    assert any(
        json.loads(path.read_bytes()) == {"dto_type": "item", "id": "item:one"}
        for path in (tmp_path / "index/staging/run-state/turn-0001/objects").rglob("*")
        if path.is_file()
    )


@pytest.mark.parametrize("operation", ["stage", "triplet", "refs", "validate", "promote", "repair"])
@pytest.mark.asyncio
async def test_direct_state_effects_refuse_event_loop_execution(tmp_path, operation):
    index = LocalSovereignIndex(str(tmp_path))
    await asyncio.to_thread(stage, index)
    before = await asyncio.to_thread(tree, tmp_path)
    calls = {
        "stage": lambda: stage(index),
        "triplet": lambda: index.read_triplet_record(
            scope="staging", stem="data/item", run_id="run-state", turn_id="turn-0001"
        ),
        "refs": lambda: index.read_refs_sources(scope="committed", ref_type="item", ref_id="item:one"),
        "validate": lambda: index.validate_links_against_index(
            run_id="run-state", turn_id="turn-0001", stem="data/item"
        ),
        "promote": lambda: promote_turn(root=str(tmp_path), run_id="run-state", turn_id="turn-0001"),
        "repair": lambda: repair_run_ledger(
            str(tmp_path), force_turn_id="turn-0007", acknowledge=REPAIR_ACKNOWLEDGEMENT
        ),
    }
    with pytest.raises(RuntimeError, match="E_KERNEL_STATE_REQUIRES_ASYNC_OWNER"):
        calls[operation]()
    assert await asyncio.to_thread(tree, tmp_path) == before


@pytest.mark.parametrize("empty_directory", [False, True])
def test_missing_or_empty_staging_preserves_committed_content(tmp_path, empty_directory):
    index = LocalSovereignIndex(str(tmp_path))
    stage(index)
    assert promote_turn(root=str(tmp_path), run_id="run-state", turn_id="turn-0001").outcome == "PASS"
    committed = tmp_path / "index/committed"
    before = tree(committed, exclude_ledger=True)
    if empty_directory:
        (tmp_path / "index/staging/run-state/turn-0002").mkdir()
    result = promote_turn(root=str(tmp_path), run_id="run-state", turn_id="turn-0002")
    assert result.outcome == "PASS"
    assert tree(committed, exclude_ledger=True) == before
    assert result.promoted_stems == [] and any("I_NOOP_PROMOTION" in line for line in result.events)
    assert json.loads((committed / "index/run_ledger.json").read_bytes())["last_promoted_turn_id"] == "turn-0002"


def test_promotion_captures_relative_root_before_ledger_io(tmp_path, monkeypatch):
    first, later = tmp_path / "first", tmp_path / "later"
    first.mkdir()
    later.mkdir()
    root = first / "state"
    index = LocalSovereignIndex(str(root))
    stage(index)
    assert promote_turn(root=str(root), run_id="run-state", turn_id="turn-0001").outcome == "PASS"
    stage(index, turn="turn-0002")
    monkeypatch.chdir(first)
    open_path = Path.open
    observed = []

    def change_cwd_after_open(path, *args, **kwargs):
        stream = open_path(path, *args, **kwargs)
        if path.name == "run_ledger.json" and not observed:
            observed.append(path)
            monkeypatch.chdir(later)
        return stream

    monkeypatch.setattr(Path, "open", change_cwd_after_open)
    result = promote_turn(root="state", run_id="run-state", turn_id="turn-0002")
    assert observed and result.outcome == "PASS"
    assert (
        json.loads((root / "index/committed/index/run_ledger.json").read_bytes())["last_promoted_turn_id"]
        == "turn-0002"
    )
    assert not (root / "index/staging/run-state/turn-0002").exists()
    assert not (later / "state").exists()
