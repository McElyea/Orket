from __future__ import annotations

from pathlib import Path


def test_contract_delta_template_contains_required_sections() -> None:
    path = Path("docs/architecture/CONTRACT_DELTA_TEMPLATE.md")
    text = path.read_text(encoding="utf-8")
    required_sections = [
        "## Delta",
        "## Migration Plan",
        "## Rollback Plan",
        "## Versioning Decision",
    ]
    missing = [section for section in required_sections if section not in text]
    assert not missing, "contract delta template missing required sections: " + ", ".join(missing)


def test_contributor_guide_references_contract_delta_template() -> None:
    text = Path("docs/CONTRIBUTOR.md").read_text(encoding="utf-8")
    assert "CONTRACT_DELTA_TEMPLATE.md" in text
