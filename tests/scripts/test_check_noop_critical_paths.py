from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_noop_critical_paths import (
    check_noop_critical_paths,
    evaluate_noop_critical_paths,
    main,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# Layer: contract
def test_evaluate_noop_critical_paths_flags_pass_and_ellipsis_functions(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    _write(
        source,
        "\n".join(
            [
                "def a() -> None:",
                "    pass",
                "",
                "def b() -> None:",
                "    ...",
            ]
        )
        + "\n",
    )

    payload = evaluate_noop_critical_paths(roots=[tmp_path])
    assert payload["ok"] is False
    names = {row["name"] for row in payload["findings"]}
    assert "a" in names
    assert "b" in names


# Layer: contract
def test_evaluate_noop_critical_paths_ignores_abstract_methods(tmp_path: Path) -> None:
    source = tmp_path / "abstracts.py"
    _write(
        source,
        "\n".join(
            [
                "from abc import ABC, abstractmethod",
                "",
                "class C(ABC):",
                "    @abstractmethod",
                "    def run(self) -> None:",
                "        pass",
            ]
        )
        + "\n",
    )

    payload = evaluate_noop_critical_paths(roots=[tmp_path])
    assert payload["ok"] is True
    assert payload["findings"] == []


# Layer: contract
def test_evaluate_noop_critical_paths_ignores_protocol_ellipsis_methods(tmp_path: Path) -> None:
    source = tmp_path / "protocol.py"
    _write(
        source,
        "\n".join(
            [
                "from typing import Protocol",
                "",
                "class Hook(Protocol):",
                "    def run(self) -> None:",
                "        ...",
            ]
        )
        + "\n",
    )

    payload = evaluate_noop_critical_paths(roots=[tmp_path])
    assert payload["ok"] is True
    assert payload["findings"] == []


# Layer: contract
def test_evaluate_noop_critical_paths_parses_utf8_bom_files(tmp_path: Path) -> None:
    source = tmp_path / "bom_file.py"
    source.write_text("def run() -> int:\n    return 1\n", encoding="utf-8-sig")
    payload = evaluate_noop_critical_paths(roots=[tmp_path])
    assert payload["ok"] is True
    assert payload["parse_errors"] == []


# Layer: integration
def test_check_noop_critical_paths_writes_out_payload_with_diff_ledger(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    _write(source, "def run() -> int:\n    return 1\n")
    out_path = tmp_path / "out" / "noop_report.json"

    exit_code, payload = check_noop_critical_paths(roots=[tmp_path], out_path=out_path)
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_failure_when_noop_detected(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    _write(source, "def noop() -> None:\n    pass\n")
    exit_code = main(["--root", str(tmp_path)])
    assert exit_code == 1
