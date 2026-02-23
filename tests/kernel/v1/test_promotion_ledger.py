from __future__ import annotations

import json
import tempfile
from pathlib import Path

from orket.kernel.v1.state.lsi import LocalSovereignIndex
from orket.kernel.v1.state.promotion import promote_turn


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

