"""Layer: integration. Native refusal, retained recovery state and partial effects."""

import json

import pytest

from orket.adapters.storage import kernel_state_store as store
from orket.kernel.v1.state.lsi import LocalSovereignIndex
from orket.kernel.v1.state.promotion import promote_turn
from tests.integration.test_kernel_state_effect_boundaries import stage, tree

pytestmark = pytest.mark.integration


def test_native_adapter_refuses_mutable_bytes_before_creating_directories(tmp_path):
    with pytest.raises(TypeError, match="E_KERNEL_STATE_IMMUTABLE_BYTES_REQUIRED"):
        store.write_bytes(tmp_path / "state/payload", bytearray(b"mutable"))
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize("stem", ["..", "../escape", "data/../../escape"])
def test_invalid_stems_refuse_before_staging_effects(tmp_path, stem):
    root = tmp_path / "state"
    index = LocalSovereignIndex(str(root))
    with pytest.raises(ValueError, match="E_KERNEL_STATE_INVALID_STEM"):
        index.stage_triplet(run_id="run-state", turn_id="turn-0001", stem=stem, body={}, links={}, manifest={})
    assert not root.exists() and tree(tmp_path) == {}


@pytest.mark.parametrize("field", ["run_id", "turn_id", "ref_type", "ref_id"])
def test_parent_identifier_segments_refuse_before_effects(tmp_path, field):
    values = dict(run_id="run-state", turn_id="turn-0001", ref_type="item", ref_id="one")
    values[field] = ".."
    index = LocalSovereignIndex(str(tmp_path))
    with pytest.raises(ValueError, match="E_KERNEL_STATE_INVALID_PATH_SEGMENT"):
        index.stage_triplet(
            run_id=values["run_id"],
            turn_id=values["turn_id"],
            stem="item",
            body={},
            links={"target": {"type": values["ref_type"], "id": values["ref_id"]}},
            manifest={},
        )
    assert tree(tmp_path) == {}


def test_lsi_root_requires_new_instance_for_another_root(tmp_path):
    index = LocalSovereignIndex(str(tmp_path / "first"))
    with pytest.raises(AttributeError):
        index.root = str(tmp_path / "second")
    stage(index)
    assert (tmp_path / "first/index").exists() and not (tmp_path / "second").exists()


@pytest.mark.parametrize("reserved", ["committed.__new", "committed.__bak"])
@pytest.mark.parametrize("noop", [False, True])
def test_promotion_preserves_preexisting_recovery_directories(tmp_path, reserved, noop):
    index = LocalSovereignIndex(str(tmp_path))
    stage(index)
    if noop:
        assert promote_turn(root=str(tmp_path), run_id="run-state", turn_id="turn-0001").outcome == "PASS"
    recovery = tmp_path / "index" / reserved
    recovery.mkdir()
    (recovery / "operator-evidence").write_bytes(b"retain this")
    before = tree(tmp_path)
    result = promote_turn(root=str(tmp_path), run_id="run-state", turn_id="turn-0002" if noop else "turn-0001")
    assert result.outcome == "FAIL" and "E_KERNEL_PROMOTION_RECOVERY_REQUIRED" in result.issues[0].details["error"]
    assert tree(tmp_path) == before


@pytest.mark.parametrize("payload", [[], {}, {"last_promoted_turn_id": "invalid"}])
def test_invalid_ledger_shape_cannot_reset_the_cursor(tmp_path, payload):
    index = LocalSovereignIndex(str(tmp_path))
    stage(index)
    assert promote_turn(root=str(tmp_path), run_id="run-state", turn_id="turn-0001").outcome == "PASS"
    ledger = tmp_path / "index/committed/index/run_ledger.json"
    ledger.write_text(json.dumps(payload), encoding="utf-8")
    before = tree(tmp_path)
    result = promote_turn(root=str(tmp_path), run_id="run-state", turn_id="turn-0001")
    assert result.outcome == "FAIL" and result.issues[0].code == "E_PROMOTION_FAILED"
    assert tree(tmp_path) == before


@pytest.mark.parametrize("contents", [b"{broken", b"[]", b"{}"])
def test_link_validation_refuses_unavailable_observed_index(tmp_path, contents):
    index = LocalSovereignIndex(str(tmp_path))
    stage(index)
    bad = tmp_path / "index/committed/triplets/bad.json"
    bad.parent.mkdir(parents=True)
    bad.write_bytes(contents)
    before = tree(tmp_path)
    with pytest.raises(ValueError, match="E_KERNEL_STATE_INDEX_UNAVAILABLE"):
        index.validate_links_against_index(run_id="run-state", turn_id="turn-0001", stem="data/item")
    assert tree(tmp_path) == before


def test_bad_reference_record_does_not_look_empty(tmp_path):
    index = LocalSovereignIndex(str(tmp_path))
    stage(index)
    bad = tmp_path / "index/staging/run-state/turn-0001/refs/by_id/item/item%3Aone.json"
    bad.write_bytes(b"[]")
    before = tree(tmp_path)
    with pytest.raises(ValueError, match="E_KERNEL_STATE_INDEX_UNAVAILABLE"):
        index.read_refs_sources(
            scope="staging", run_id="run-state", turn_id="turn-0001", ref_type="item", ref_id="item:one"
        )
    assert tree(tmp_path) == before


def test_missing_staged_links_object_refuses_before_candidate_publication(tmp_path):
    index = LocalSovereignIndex(str(tmp_path))
    digests = stage(index)
    scope = tmp_path / "index/staging/run-state/turn-0001"
    (scope / "objects" / digests.links_digest[:2] / digests.links_digest).unlink()
    before = tree(tmp_path)
    result = promote_turn(root=str(tmp_path), run_id="run-state", turn_id="turn-0001")
    assert result.outcome == "FAIL" and result.issues[0].code == "E_PROMOTION_FAILED"
    assert tree(tmp_path) == before
    assert not (tmp_path / "index/committed").exists() and not (tmp_path / "index/committed.__new").exists()


def test_promotion_cannot_discard_corrupt_existing_reference_sources(tmp_path):
    index = LocalSovereignIndex(str(tmp_path))
    stage(index)
    assert promote_turn(root=str(tmp_path), run_id="run-state", turn_id="turn-0001").outcome == "PASS"
    path = tmp_path / "index/committed/refs/by_id/item/item%3Aone.json"
    path.write_bytes(b'{"sources":null}')
    before = tree(tmp_path / "index/committed")
    stage(index, turn="turn-0002")
    result = promote_turn(root=str(tmp_path), run_id="run-state", turn_id="turn-0002")
    assert result.outcome == "FAIL" and "E_KERNEL_STATE_INDEX_UNAVAILABLE" in result.issues[0].details["error"]
    assert tree(tmp_path / "index/committed") == before
    assert not (tmp_path / "index/committed.__new").exists()


def test_failed_candidate_cleanup_is_reported_and_retained(tmp_path, monkeypatch):
    index = LocalSovereignIndex(str(tmp_path))
    stage(index)

    def fail_copy(*_args):
        raise OSError("candidate copy failed")

    def fail_cleanup(*_args):
        raise PermissionError("candidate cleanup refused")

    monkeypatch.setattr(store, "copy_file", fail_copy)
    monkeypatch.setattr(store, "remove_tree", fail_cleanup)
    result = promote_turn(root=str(tmp_path), run_id="run-state", turn_id="turn-0001")
    assert result.outcome == "FAIL"
    assert [issue.code for issue in result.issues] == ["E_PROMOTION_FAILED", "E_PROMOTION_CLEANUP_FAILED"]
    assert "candidate copy failed" in result.issues[0].details["error"]
    assert "candidate cleanup refused" in result.issues[1].details["error"]
    assert (tmp_path / "index/committed.__new").exists() and not (tmp_path / "index/committed").exists()
    retry = promote_turn(root=str(tmp_path), run_id="run-state", turn_id="turn-0001")
    assert retry.outcome == "FAIL" and "RECOVERY_REQUIRED" in retry.issues[0].details["error"]


def test_second_directory_replace_failure_retains_original_backup(tmp_path, monkeypatch):
    index = LocalSovereignIndex(str(tmp_path))
    stage(index)
    assert promote_turn(root=str(tmp_path), run_id="run-state", turn_id="turn-0001").outcome == "PASS"
    before = tree(tmp_path / "index/committed")
    stage(index, turn="turn-0002")
    replace = store.replace
    observed = []

    def fail_second(source, destination):
        observed.append(source)
        if source.name == "committed.__new":
            raise OSError("second directory replacement failed")
        replace(source, destination)

    monkeypatch.setattr(store, "replace", fail_second)
    result = promote_turn(root=str(tmp_path), run_id="run-state", turn_id="turn-0002")
    assert result.outcome == "FAIL" and len(observed) == 2
    assert tree(tmp_path / "index/committed.__bak") == before
    assert not (tmp_path / "index/committed").exists()
    assert not (tmp_path / "index/committed.__new").exists()
    assert (tmp_path / "index/staging/run-state/turn-0002").exists()


def test_cleanup_failure_after_publication_does_not_claim_rollback(tmp_path, monkeypatch):
    index = LocalSovereignIndex(str(tmp_path))
    stage(index)
    assert promote_turn(root=str(tmp_path), run_id="run-state", turn_id="turn-0001").outcome == "PASS"
    old = tree(tmp_path / "index/committed")
    stage(index, turn="turn-0002")
    remove = store.remove_tree

    def fail_backup(path):
        if path.name == "committed.__bak":
            raise OSError("published backup cleanup failed")
        remove(path)

    monkeypatch.setattr(store, "remove_tree", fail_backup)
    result = promote_turn(root=str(tmp_path), run_id="run-state", turn_id="turn-0002")
    assert result.outcome == "FAIL" and "backup cleanup failed" in result.issues[0].details["error"]
    assert (
        json.loads((tmp_path / "index/committed/index/run_ledger.json").read_bytes())["last_promoted_turn_id"]
        == "turn-0002"
    )
    assert tree(tmp_path / "index/committed.__bak") == old
    assert (tmp_path / "index/staging/run-state/turn-0002").exists()
