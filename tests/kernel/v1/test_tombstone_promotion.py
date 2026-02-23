from __future__ import annotations

import json
import tempfile
from pathlib import Path

from orket.kernel.v1.state.lsi import LocalSovereignIndex
from orket.kernel.v1.state.promotion import promote_turn


def _write_tombstone(root: Path, run_id: str, turn_id: str, stem: str, payload: dict) -> Path:
    tombstone_path = (
        root
        / "index"
        / "staging"
        / run_id
        / turn_id
        / "triplets"
        / Path(stem).with_suffix("").as_posix()
    )
    file_path = Path(str(tombstone_path) + ".tombstone.json")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    return file_path


def test_valid_tombstone_prunes_refs_and_removes_triplet_record() -> None:
    with tempfile.TemporaryDirectory(prefix="orket_tombstone_valid_") as tmp:
        root = Path(tmp)
        lsi = LocalSovereignIndex(str(root))
        run_id = "run-4000"
        stem = "data/dto/t/subject"

        lsi.stage_triplet(
            run_id=run_id,
            turn_id="turn-0001",
            stem=stem,
            body={"dto_type": "invocation", "id": "inv:tomb"},
            links={"declares": {"type": "skill", "id": "skill:tomb", "relationship": "declares"}},
            manifest={},
        )
        first = promote_turn(root=str(root), run_id=run_id, turn_id="turn-0001")
        assert first.outcome == "PASS"

        _write_tombstone(
            root,
            run_id,
            "turn-0002",
            stem,
            {
                "kind": "tombstone",
                "stem": stem,
                "dto_type": "invocation",
                "id": "inv:tomb",
                "deleted_by_turn_id": "turn-0002",
            },
        )

        second = promote_turn(root=str(root), run_id=run_id, turn_id="turn-0002")
        assert second.outcome == "PASS"
        assert not second.issues

        ref_path = root / "index" / "committed" / "refs" / "by_id" / "skill" / "skill%3Atomb.json"
        ref_payload = json.loads(ref_path.read_text(encoding="utf-8"))
        assert ref_payload.get("sources") == []

        triplet_path = root / "index" / "committed" / "triplets" / "data" / "dto" / "t" / "subject.json"
        assert not triplet_path.exists()


def test_tombstone_invalid_payload_fails_with_promotion_stage_code() -> None:
    with tempfile.TemporaryDirectory(prefix="orket_tombstone_invalid_") as tmp:
        root = Path(tmp)
        run_id = "run-4001"
        stem = "data/dto/t/invalid"

        _write_tombstone(
            root,
            run_id,
            "turn-0001",
            stem,
            {"kind": "tombstone", "stem": stem},
        )
        result = promote_turn(root=str(root), run_id=run_id, turn_id="turn-0001")
        assert result.outcome == "FAIL"
        assert any(issue.code == "E_TOMBSTONE_INVALID" and issue.stage == "promotion" for issue in result.issues)


def test_tombstone_stem_mismatch_fails_with_promotion_stage_code() -> None:
    with tempfile.TemporaryDirectory(prefix="orket_tombstone_mismatch_") as tmp:
        root = Path(tmp)
        run_id = "run-4002"
        stem = "data/dto/t/mismatch"

        _write_tombstone(
            root,
            run_id,
            "turn-0001",
            stem,
            {
                "kind": "tombstone",
                "stem": "data/dto/t/other",
                "dto_type": "invocation",
                "id": "inv:mismatch",
                "deleted_by_turn_id": "turn-0001",
            },
        )
        result = promote_turn(root=str(root), run_id=run_id, turn_id="turn-0001")
        assert result.outcome == "FAIL"
        assert any(issue.code == "E_TOMBSTONE_STEM_MISMATCH" and issue.stage == "promotion" for issue in result.issues)

