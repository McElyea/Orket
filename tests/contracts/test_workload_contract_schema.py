from __future__ import annotations

from pathlib import Path


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_refactor_card_engine_workload_contract_doc_exists_and_contains_required_tokens() -> None:
    path = Path("docs/projects/RefactorCardEngine/03-WORKLOAD-CONTRACT.md")
    assert path.exists(), f"Missing workload contract doc: {path}"
    text = _read(path)

    required_tokens = [
        "workload.contract.v1",
        "workload_contract_version",
        "workload_type",
        "units",
        "required_materials",
        "expected_artifacts",
        "validators",
        "summary_targets",
        "provenance_targets",
        "ODR",
        "Cards",
    ]
    missing = [token for token in required_tokens if token not in text]
    assert not missing, f"Missing required workload contract tokens: {missing}"


def test_refactor_card_engine_workload_contract_schema_file_exists() -> None:
    path = Path("docs/projects/RefactorCardEngine/workload-contract-v1.schema.json")
    assert path.exists(), f"Missing workload contract schema: {path}"
