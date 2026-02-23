from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from orket.kernel.v1.state.lsi import LocalSovereignIndex
from orket.kernel.v1.state.promotion import promote_turn


CODE_TOKEN_RE = re.compile(r"\[CODE:([A-Z0-9_]+)\]")
CODE_PATTERN_RE = re.compile(r"^[EI]_[A-Z0-9_]+$")


def _registry_codes() -> list[str]:
    payload = json.loads(Path("docs/projects/OS/contracts/error-codes-v1.json").read_text(encoding="utf-8"))
    return [code for code in payload["codes"] if isinstance(code, str)]


def _extract_event_codes(events: list[str]) -> set[str]:
    found: set[str] = set()
    for event in events:
        for match in CODE_TOKEN_RE.finditer(event):
            found.add(match.group(1))
    return found


def test_registry_integrity_and_ordering() -> None:
    codes = _registry_codes()
    assert codes == sorted(codes), "Violation: Registry codes must be sorted deterministically."
    assert len(codes) == len(set(codes)), "Violation: Registry contains duplicate code entries."
    bad = [code for code in codes if not CODE_PATTERN_RE.fullmatch(code)]
    assert not bad, f"Violation: Invalid code token(s) in registry: {bad}"


def test_emitted_issue_and_event_codes_are_registered() -> None:
    codes = set(_registry_codes())
    emitted_codes: set[str] = set()

    with tempfile.TemporaryDirectory(prefix="orket_registry_test_") as tmp:
        root = Path(tmp)
        lsi = LocalSovereignIndex(str(root))

        # Successful stage/promote path.
        lsi.stage_triplet(
            run_id="run-1000",
            turn_id="turn-0001",
            stem="data/dto/r/ok",
            body={"dto_type": "invocation", "id": "inv:ok"},
            links={"declares": {"type": "skill", "id": "skill:alpha", "relationship": "declares"}},
            manifest={},
        )
        ok = promote_turn(root=str(root), run_id="run-1000", turn_id="turn-0001")
        emitted_codes |= _extract_event_codes(ok.events)
        emitted_codes |= {issue.code for issue in ok.issues}

        # Out-of-order promotion failure.
        out_of_order = promote_turn(root=str(root), run_id="run-1000", turn_id="turn-0003")
        emitted_codes |= _extract_event_codes(out_of_order.events)
        emitted_codes |= {issue.code for issue in out_of_order.issues}

        # Orphan target validation failure.
        lsi.stage_triplet(
            run_id="run-1001",
            turn_id="turn-0001",
            stem="data/dto/r/orphan",
            body={"dto_type": "invocation", "id": "inv:orphan"},
            links={"declares": {"type": "skill", "id": "skill:does-not-exist", "relationship": "declares"}},
            manifest={},
        )
        outcome, issues, events = lsi.validate_links_against_index(
            run_id="run-1001",
            turn_id="turn-0001",
            stem="data/dto/r/orphan",
        )
        assert outcome == "FAIL"
        emitted_codes |= _extract_event_codes(events)
        emitted_codes |= {issue.code for issue in issues}

    missing = sorted(code for code in emitted_codes if code not in codes)
    assert not missing, (
        "Violation: Emitted code(s) are not registered in "
        f"docs/projects/OS/contracts/error-codes-v1.json: {missing}"
    )

