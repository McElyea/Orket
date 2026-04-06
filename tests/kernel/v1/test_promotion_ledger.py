from __future__ import annotations

import json
import tempfile
from pathlib import Path

from orket.kernel.v1.state.lsi import LocalSovereignIndex
from orket.kernel.v1.state.promotion import REPAIR_ACKNOWLEDGEMENT, promote_turn, repair_run_ledger


def test_run_ledger_written_and_advanced_on_promotion() -> None:
    with tempfile.TemporaryDirectory(prefix="orket_ledger_test_") as tmp:
        root = Path(tmp)
        lsi = LocalSovereignIndex(str(root))

        lsi.stage_triplet(
            run_id="run-2000",
            turn_id="turn-0001",
            stem="data/dto/l/one",
            body={"dto_type": "invocation", "id": "inv:one"},
            links={"declares": {"type": "skill", "id": "skill:one", "relationship": "declares"}},
            manifest={},
        )
        result = promote_turn(root=str(root), run_id="run-2000", turn_id="turn-0001")
        assert result.outcome == "PASS"

        ledger = root / "index" / "committed" / "index" / "run_ledger.json"
        assert ledger.exists(), "run_ledger.json must exist after first successful promotion."
        payload = json.loads(ledger.read_text(encoding="utf-8"))
        assert payload["last_promoted_turn_id"] == "turn-0001"

        # Missing staging root for turn-0002 still advances ledger via deterministic no-op/deletion path.
        result2 = promote_turn(root=str(root), run_id="run-2000", turn_id="turn-0002")
        assert result2.outcome == "PASS"
        payload2 = json.loads(ledger.read_text(encoding="utf-8"))
        assert payload2["last_promoted_turn_id"] == "turn-0002"


def test_out_of_order_and_duplicate_promotions_fail_with_promotion_stage_codes() -> None:
    with tempfile.TemporaryDirectory(prefix="orket_ledger_order_test_") as tmp:
        root = Path(tmp)
        lsi = LocalSovereignIndex(str(root))

        lsi.stage_triplet(
            run_id="run-2001",
            turn_id="turn-0001",
            stem="data/dto/l/two",
            body={"dto_type": "invocation", "id": "inv:two"},
            links={"declares": {"type": "skill", "id": "skill:two", "relationship": "declares"}},
            manifest={},
        )
        ok = promote_turn(root=str(root), run_id="run-2001", turn_id="turn-0001")
        assert ok.outcome == "PASS"

        out_of_order = promote_turn(root=str(root), run_id="run-2001", turn_id="turn-0003")
        assert out_of_order.outcome == "FAIL"
        assert any(issue.code == "E_PROMOTION_OUT_OF_ORDER" for issue in out_of_order.issues)
        assert all(issue.stage == "promotion" for issue in out_of_order.issues)

        duplicate = promote_turn(root=str(root), run_id="run-2001", turn_id="turn-0001")
        assert duplicate.outcome == "FAIL"
        assert any(issue.code == "E_PROMOTION_ALREADY_APPLIED" for issue in duplicate.issues)
        assert all(issue.stage == "promotion" for issue in duplicate.issues)


def test_corrupt_run_ledger_fails_closed_instead_of_resetting_to_turn_zero() -> None:
    with tempfile.TemporaryDirectory(prefix="orket_ledger_corrupt_test_") as tmp:
        root = Path(tmp)
        lsi = LocalSovereignIndex(str(root))
        lsi.stage_triplet(
            run_id="run-2002",
            turn_id="turn-0001",
            stem="data/dto/l/corrupt",
            body={"dto_type": "invocation", "id": "inv:corrupt"},
            links={"declares": {"type": "skill", "id": "skill:corrupt", "relationship": "declares"}},
            manifest={},
        )
        assert promote_turn(root=str(root), run_id="run-2002", turn_id="turn-0001").outcome == "PASS"

        ledger = root / "index" / "committed" / "index" / "run_ledger.json"
        ledger.write_text("{\"last_promoted_turn_id\":", encoding="utf-8")
        result = promote_turn(root=str(root), run_id="run-2002", turn_id="turn-0002")

        assert result.outcome == "FAIL"
        assert any(issue.code == "E_PROMOTION_FAILED" for issue in result.issues)


def test_repair_run_ledger_advances_promotion_cursor_after_gap_acknowledgement() -> None:
    with tempfile.TemporaryDirectory(prefix="orket_ledger_repair_test_") as tmp:
        root = Path(tmp)
        repair_run_ledger(str(root), force_turn_id="turn-0007", acknowledge=REPAIR_ACKNOWLEDGEMENT)

        ledger = root / "index" / "committed" / "index" / "run_ledger.json"
        payload = json.loads(ledger.read_text(encoding="utf-8"))

        assert payload["last_promoted_turn_id"] == "turn-0007"
