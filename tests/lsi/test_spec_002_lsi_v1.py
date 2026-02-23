from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import pytest

from .adapter import LSIAdapter
from orket.kernel.v1.canonical import canonical_json_bytes, structural_digest


def _to_plain(obj: Any) -> Any:
    if obj is None:
        return None
    if is_dataclass(obj):
        return asdict(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return obj
    return obj


def _result_outcome(result: Any) -> str | None:
    r = _to_plain(result)
    if isinstance(r, dict):
        return r.get("outcome") or r.get("status")
    return None


def _result_events(result: Any) -> list[str]:
    r = _to_plain(result)
    if isinstance(r, dict):
        ev = r.get("events")
        if isinstance(ev, list):
            return [str(x) for x in ev]
    return []


def _result_issues(result: Any) -> list[dict[str, Any]]:
    r = _to_plain(result)
    if isinstance(r, dict):
        issues = r.get("issues") or r.get("errors")
        if isinstance(issues, list):
            return [_to_plain(x) for x in issues]
    return []


def _must_fail(callable_fn, *args, **kwargs) -> Any:
    try:
        result = callable_fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return exc
    outcome = _result_outcome(result)
    assert outcome in ("FAIL", "ERROR"), f"Expected FAIL/ERROR but got: {outcome} ({result})"
    return result


def _must_pass(callable_fn, *args, **kwargs) -> Any:
    result = callable_fn(*args, **kwargs)
    outcome = _result_outcome(result)
    if outcome is not None:
        assert outcome == "PASS", f"Expected PASS but got: {outcome} ({result})"
    return result


def _find_committed_root(tmp_root: Path) -> Path:
    candidates = [
        tmp_root / "index" / "committed",
        tmp_root / "committed",
    ]
    for c in candidates:
        if c.exists():
            return c
    return tmp_root / "index" / "committed"


def _find_staging_root(tmp_root: Path, run_id: str, turn_id: str) -> Path:
    candidates = [
        tmp_root / "index" / "staging" / run_id / turn_id,
        tmp_root / "staging" / run_id / turn_id,
        tmp_root / "index" / "staging" / run_id.replace(":", "%3A") / turn_id.replace(":", "%3A"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return tmp_root / "index" / "staging" / run_id / turn_id


def _snapshot_tree(path: Path) -> dict[str, tuple[int, float]]:
    snap: dict[str, tuple[int, float]] = {}
    if not path.exists():
        return snap
    for p in sorted(path.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(path)).replace("\\", "/")
            stat = p.stat()
            snap[rel] = (stat.st_size, stat.st_mtime)
    return snap


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture()
def lsi_adapter(tmp_path: Path) -> LSIAdapter:
    return LSIAdapter(tmp_path)


def test_law_1_fortress_invariant_read_committed_write_staging(lsi_adapter: LSIAdapter, tmp_path: Path):
    run_id = "run-0001"
    turn_id = "turn-0001"

    committed = _find_committed_root(tmp_path)
    committed_before = _snapshot_tree(committed)

    lsi_adapter.stage(
        stem="data/dto/a/invocation_1",
        body={"dto_type": "invocation", "id": "inv:1"},
        links={"declares": {"type": "skill", "id": "skill:alpha", "relationship": "declares"}},
        run_id=run_id,
        turn_id=turn_id,
    )

    committed_after = _snapshot_tree(committed)
    assert committed_after == committed_before

    staging = _find_staging_root(tmp_path, run_id, turn_id)
    assert staging.exists()


def test_law_2_process_model_sequential_promotion_enforced(lsi_adapter: LSIAdapter):
    run_id = "run-0002"

    lsi_adapter.stage(
        stem="data/dto/a/invocation_seq",
        body={"dto_type": "invocation", "id": "inv:seq"},
        links={},
        run_id=run_id,
        turn_id="turn-0001",
    )
    lsi_adapter.stage(
        stem="data/dto/a/invocation_seq",
        body={"dto_type": "invocation", "id": "inv:seq2"},
        links={},
        run_id=run_id,
        turn_id="turn-0002",
    )

    _must_fail(lsi_adapter.promote, run_id=run_id, turn_id="turn-0002")


def test_law_3_identity_physics_byte_match_digest():
    obj = {"b": 2, "a": 1, "unicode": "Delta"}
    b = canonical_json_bytes(obj)
    expected = hashlib.sha256(b).hexdigest()
    got = structural_digest(b)
    assert got == expected
    assert b.decode("utf-8") == '{"a":1,"b":2,"unicode":"Delta"}'


def test_law_4_record_version_required_after_promotion(lsi_adapter: LSIAdapter, tmp_path: Path):
    run_id = "run-0003"
    turn_id = "turn-0001"

    lsi_adapter.stage(
        stem="data/dto/v/version_check",
        body={"dto_type": "invocation", "id": "inv:v1"},
        links={"declares": {"type": "skill", "id": "skill:one", "relationship": "declares"}},
        run_id=run_id,
        turn_id=turn_id,
    )
    _must_pass(lsi_adapter.promote, run_id=run_id, turn_id=turn_id)

    committed = _find_committed_root(tmp_path)

    triplets_dir = committed / "triplets"
    refs_dir = committed / "refs" / "by_id"
    assert triplets_dir.exists()
    assert refs_dir.exists()

    triplet_files = sorted(triplets_dir.rglob("*.json"))
    ref_files = sorted(refs_dir.rglob("*.json"))
    assert triplet_files
    assert ref_files

    t = _read_json(triplet_files[0])
    r = _read_json(ref_files[0])

    assert t.get("lsi_version") == "lsi/v1"
    assert r.get("lsi_version") == "lsi/v1"


def test_law_5_pruning_is_stem_scoped_no_ghost_refs(lsi_adapter: LSIAdapter, tmp_path: Path):
    run_id = "run-0004"

    lsi_adapter.stage(
        stem="data/dto/p/prune_stem",
        body={"dto_type": "invocation", "id": "inv:p1"},
        links={"declares": {"type": "skill", "id": "skill:alpha", "relationship": "declares"}},
        run_id=run_id,
        turn_id="turn-0001",
    )
    _must_pass(lsi_adapter.promote, run_id=run_id, turn_id="turn-0001")

    committed = _find_committed_root(tmp_path)
    alpha_ref = committed / "refs" / "by_id" / "skill" / "skill%3Aalpha.json"
    assert alpha_ref.exists()

    alpha_before = _read_json(alpha_ref)
    sources_before = alpha_before.get("sources", [])
    assert any(s.get("stem") == "data/dto/p/prune_stem" for s in sources_before)

    lsi_adapter.stage(
        stem="data/dto/p/prune_stem",
        body={"dto_type": "invocation", "id": "inv:p2"},
        links={"declares": {"type": "skill", "id": "skill:beta", "relationship": "declares"}},
        run_id=run_id,
        turn_id="turn-0002",
    )
    _must_pass(lsi_adapter.promote, run_id=run_id, turn_id="turn-0002")

    alpha_after = _read_json(alpha_ref)
    sources_after = alpha_after.get("sources", [])
    assert not any(s.get("stem") == "data/dto/p/prune_stem" for s in sources_after)


def test_law_6_deletion_is_staged_tombstone_prunes_refs(lsi_adapter: LSIAdapter, tmp_path: Path):
    run_id = "run-0005"

    lsi_adapter.stage(
        stem="data/dto/d/delete_me",
        body={"dto_type": "invocation", "id": "inv:del"},
        links={"declares": {"type": "skill", "id": "skill:gone", "relationship": "declares"}},
        run_id=run_id,
        turn_id="turn-0001",
    )
    _must_pass(lsi_adapter.promote, run_id=run_id, turn_id="turn-0001")

    committed = _find_committed_root(tmp_path)
    gone_ref = committed / "refs" / "by_id" / "skill" / "skill%3Agone.json"
    assert gone_ref.exists()

    _must_pass(lsi_adapter.promote, run_id=run_id, turn_id="turn-0002")

    gone_after = _read_json(gone_ref)
    sources_after = gone_after.get("sources", [])
    assert not any(s.get("stem") == "data/dto/d/delete_me" for s in sources_after)


def test_law_7_atomic_promotion_all_or_nothing(lsi_adapter: LSIAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    run_id = "run-0006"
    turn_id = "turn-0001"

    committed = _find_committed_root(tmp_path)
    before = _snapshot_tree(committed)

    lsi_adapter.stage(
        stem="data/dto/a/atomic",
        body={"dto_type": "invocation", "id": "inv:atomic"},
        links={"declares": {"type": "skill", "id": "skill:atomic", "relationship": "declares"}},
        run_id=run_id,
        turn_id=turn_id,
    )

    def boom(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        raise RuntimeError("simulated swap failure")

    monkeypatch.setattr(os, "replace", boom)

    _must_fail(lsi_adapter.promote, run_id=run_id, turn_id=turn_id)

    after = _snapshot_tree(committed)
    assert after == before


def test_law_8_collision_is_observable_not_fatal(lsi_adapter: LSIAdapter):
    run_id = "run-0007"
    turn_id = "turn-0001"

    shared = {"type": "skill", "id": "skill:shared", "relationship": "declares"}

    lsi_adapter.stage(
        stem="data/dto/collision/a",
        body={"dto_type": "invocation", "id": "inv:ca"},
        links={"declares": shared},
        run_id=run_id,
        turn_id=turn_id,
    )
    lsi_adapter.stage(
        stem="data/dto/collision/b",
        body={"dto_type": "invocation", "id": "inv:cb"},
        links={"declares": shared},
        run_id=run_id,
        turn_id=turn_id,
    )

    result = _must_pass(lsi_adapter.promote, run_id=run_id, turn_id=turn_id)
    events = _result_events(result)

    assert any("I_REF_MULTISOURCE" in e for e in events)


def test_link_integrity_orphan_fails_with_pointer(lsi_adapter: LSIAdapter):
    run_id = "run-0008"
    turn_id = "turn-0001"

    lsi_adapter.stage(
        stem="data/dto/o/orphan",
        body={"dto_type": "invocation", "id": "inv:orphan"},
        links={"declares": {"type": "skill", "id": "skill:does-not-exist", "relationship": "declares"}},
        run_id=run_id,
        turn_id=turn_id,
    )

    result_or_exc = _must_fail(lsi_adapter.validate, stem="data/dto/o/orphan", run_id=run_id, turn_id=turn_id)

    if isinstance(result_or_exc, Exception):
        return

    issues = _result_issues(result_or_exc)
    assert issues

    orphan = None
    for issue in issues:
        code = issue.get("code") or ""
        if "ORPHAN" in code:
            orphan = issue
            break
    assert orphan is not None

    loc = orphan.get("location")
    assert isinstance(loc, str) and loc.startswith("/")
    assert "/links" in loc
