from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_unreachable_branches import (
    check_unreachable_branches,
    evaluate_unreachable_branches,
    main,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# Layer: contract
def test_evaluate_unreachable_branches_flags_constant_false_and_true_else(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    _write(
        source,
        "\n".join(
            [
                "def run(flag: bool) -> int:",
                "    if False:",
                "        return 1",
                "    if True:",
                "        return 2",
                "    else:",
                "        return 3",
                "    return 4",
            ]
        )
        + "\n",
    )

    payload = evaluate_unreachable_branches(roots=[tmp_path])
    assert payload["ok"] is False
    kinds = {row["kind"] for row in payload["findings"]}
    assert "if_body_unreachable" in kinds
    assert "if_else_unreachable" in kinds


# Layer: contract
def test_evaluate_unreachable_branches_ignores_type_checking_guards(tmp_path: Path) -> None:
    source = tmp_path / "typing_guard.py"
    _write(
        source,
        "\n".join(
            [
                "from typing import TYPE_CHECKING",
                "if TYPE_CHECKING:",
                "    from foo import bar",
                "",
                "def run() -> int:",
                "    return 1",
            ]
        )
        + "\n",
    )

    payload = evaluate_unreachable_branches(roots=[tmp_path])
    assert payload["ok"] is True
    assert payload["findings"] == []


# Layer: contract
def test_evaluate_unreachable_branches_parses_utf8_bom_files(tmp_path: Path) -> None:
    source = tmp_path / "bom_file.py"
    source.write_text("def run() -> int:\n    return 1\n", encoding="utf-8-sig")
    payload = evaluate_unreachable_branches(roots=[tmp_path])
    assert payload["ok"] is True
    assert payload["parse_errors"] == []


# Layer: integration
def test_check_unreachable_branches_writes_out_payload_with_diff_ledger(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    _write(source, "def run() -> int:\n    return 1\n")
    out_path = tmp_path / "out" / "unreachable_report.json"

    exit_code, payload = check_unreachable_branches(roots=[tmp_path], out_path=out_path)
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_failure_when_unreachable_branch_detected(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    _write(source, "if False:\n    x = 1\n")
    exit_code = main(["--root", str(tmp_path)])
    assert exit_code == 1
