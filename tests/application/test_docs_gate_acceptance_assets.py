from __future__ import annotations

from pathlib import Path


def test_docs_gate_acceptance_scripts_exist() -> None:
    required = [
        "tests/acceptance/docs_gate/_lib.sh",
        "tests/acceptance/docs_gate/DL0_clean_pass.sh",
        "tests/acceptance/docs_gate/DL1_broken_link.sh",
        "tests/acceptance/docs_gate/DL2_missing_canonical.sh",
        "tests/acceptance/docs_gate/DL3_missing_header_field.sh",
        "tests/acceptance/docs_gate/run.sh",
    ]
    missing = [path for path in required if not Path(path).exists()]
    assert not missing, "missing docs gate acceptance scripts: " + ", ".join(missing)
