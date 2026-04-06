from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

AUTHORITY_PATH = Path("CURRENT_AUTHORITY.md")
AGENTS_PATH = Path("AGENTS.md")


def _extract_json_payload(markdown_text: str) -> dict[str, Any]:
    match = re.search(r"```json\s*(\{.*?\})\s*```", markdown_text, flags=re.DOTALL)
    assert match, "CURRENT_AUTHORITY.md must include one fenced JSON payload."
    return json.loads(match.group(1))


def _load_authority_payload() -> tuple[str, dict[str, Any]]:
    markdown_text = AUTHORITY_PATH.read_text(encoding="utf-8")
    payload = _extract_json_payload(markdown_text)
    return markdown_text, payload


def _extract_current_canonical_paths_block(markdown_text: str) -> str:
    marker = "## Current Canonical Paths"
    start_index = markdown_text.find(marker)
    assert start_index >= 0, "CURRENT_AUTHORITY.md must include '## Current Canonical Paths'."
    block = markdown_text[start_index + len(marker) :]
    next_header = re.search(r"^\s*##\s+", block, flags=re.MULTILINE)
    if next_header:
        block = block[: next_header.start()]
    return block


def test_contract_current_authority_payload_shape() -> None:
    """Layer: contract."""
    _, payload = _load_authority_payload()
    assert payload.get("version") == 1
    for key in ("version", "last_updated", "authority"):
        assert key in payload

    authority = payload["authority"]
    required_sections = (
        "dependency_authority",
        "install_bootstrap",
        "runtime_entrypoints",
        "canonical_test_command",
        "verification_policy",
        "active_spec_index",
        "canonical_script_output_locations",
    )
    missing_sections = [section for section in required_sections if section not in authority]
    assert not missing_sections, "missing required authority sections: " + ", ".join(missing_sections)

    date.fromisoformat(payload["last_updated"])


def test_contract_current_authority_dates_are_in_sync() -> None:
    """Layer: contract."""
    markdown_text, payload = _load_authority_payload()
    match = re.search(r"^Last updated:\s*(\d{4}-\d{2}-\d{2})\s*$", markdown_text, flags=re.MULTILINE)
    assert match, "CURRENT_AUTHORITY.md must include a 'Last updated: YYYY-MM-DD' line."
    assert match.group(1) == payload["last_updated"]


def test_contract_current_authority_summary_sections_present() -> None:
    """Layer: contract."""
    markdown_text, _ = _load_authority_payload()
    assert "This file does not define:" in markdown_text
    assert "## Current Canonical Paths" in markdown_text
    assert "## Drift Rule" in markdown_text


def test_contract_current_authority_summary_matches_json() -> None:
    """Layer: contract."""
    markdown_text, payload = _load_authority_payload()
    authority = payload["authority"]
    summary_block = _extract_current_canonical_paths_block(markdown_text)

    expected_values = (
        authority["dependency_authority"]["install_command"],
        authority["runtime_entrypoints"]["cli_default"],
        authority["runtime_entrypoints"]["cli_named_card"],
        authority["runtime_entrypoints"]["api"],
        authority["canonical_test_command"]["command"],
        authority["active_spec_index"]["root_docs_index"],
        authority["active_spec_index"]["active_roadmap_source"],
        authority["active_spec_index"]["process_source"],
        authority["canonical_script_output_locations"]["published_artifacts_index"],
    )
    missing_values = [value for value in expected_values if value not in summary_block]
    assert not missing_values, "Current Canonical Paths summary is missing JSON values: " + ", ".join(missing_values)
    assert authority["runtime_entrypoints"]["cli_legacy_named_rock_alias"] not in summary_block


def test_contract_current_authority_paths_exist() -> None:
    """Layer: contract."""
    _, payload = _load_authority_payload()
    authority = payload["authority"]

    existing_paths: set[str] = set()

    dependency = authority["dependency_authority"]
    existing_paths.add(dependency["primary"])
    existing_paths.update(dependency.get("sources", []))

    install = authority["install_bootstrap"]
    existing_paths.update(install.get("sources", []))

    runtime = authority["runtime_entrypoints"]
    existing_paths.update(runtime.get("sources", []))

    test_cmd = authority["canonical_test_command"]
    existing_paths.add(test_cmd["lane_reference"])
    existing_paths.update(test_cmd.get("sources", []))

    verification = authority["verification_policy"]
    existing_paths.add(verification["agent_policy"])
    existing_paths.add(verification["contributor_policy"])
    existing_paths.add(verification["testing_policy"])
    existing_paths.update(verification.get("sources", []))

    spec = authority["active_spec_index"]
    existing_paths.add(spec["root_docs_index"])
    existing_paths.add(spec["active_roadmap_source"])
    existing_paths.add(spec["process_source"])
    existing_paths.add(spec["local_prompting_contract_source"])
    existing_paths.update(spec.get("sources", []))

    script_outputs = authority["canonical_script_output_locations"]
    existing_paths.add(script_outputs["published_artifacts_index"])
    existing_paths.add(script_outputs["published_artifacts_readme"])
    existing_paths.update(script_outputs.get("sources", []))

    missing_paths = [path_text for path_text in sorted(existing_paths) if not Path(path_text).exists()]
    assert not missing_paths, "CURRENT_AUTHORITY.md references missing paths: " + ", ".join(missing_paths)


def test_contract_current_authority_run_evidence_graph_view_posture() -> None:
    """Layer: contract."""
    _, payload = _load_authority_payload()
    script_outputs = payload["authority"]["canonical_script_output_locations"]
    assert script_outputs["run_evidence_graph_default_views"] == [
        "full_lineage",
        "failure_path",
        "resource_authority_path",
        "closure_path",
    ]
    assert script_outputs["run_evidence_graph_admitted_view_tokens"] == [
        "full_lineage",
        "failure_path",
        "authority",
        "decision",
        "resource_authority_path",
        "closure_path",
    ]


def test_contract_agents_references_current_authority_map() -> None:
    """Layer: contract."""
    agents_text = AGENTS_PATH.read_text(encoding="utf-8")
    assert "CURRENT_AUTHORITY.md" in agents_text
