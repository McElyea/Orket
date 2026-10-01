"""Structural authority checks; source declarations are not execution acceptance."""

import ast
from pathlib import Path

import pytest

from scripts.governance.current_authority import HISTORY, VIEW, digest, validate
from scripts.governance.current_authority_view import render

pytestmark = pytest.mark.contract


def test_current_authority_view_matches_validated_current_sources() -> None:
    payload, sources, bindings = validate(Path.cwd())
    assert Path(VIEW).read_bytes() == render(payload)
    assert bindings["command.api"].startswith("server.py#main")
    assert bindings["command.runtime"].startswith("orket/cli.py#main")
    assert not any("--rock" in row["command"] for row in payload["records"] if row["kind"] == "command")
    assert all(row["state"] in {"unavailable", "historical"}
               for row in payload["records"] if row["kind"] == "proof")
    sources.recheck()


def test_pre_cutover_history_and_agent_entrypoint_are_preserved() -> None:
    payload, _, _ = validate(Path.cwd())
    assert digest(Path(HISTORY).read_bytes()) == payload["history"]["sha256"]
    assert "CURRENT_AUTHORITY.md" in Path("AGENTS.md").read_text(encoding="utf-8")


def test_graph_view_tokens_remain_owned_by_the_canonical_graph_module() -> None:
    tree = ast.parse(Path("orket/runtime/evidence/run_evidence_graph.py").read_text(encoding="utf-8"))
    names = {"RUN_EVIDENCE_GRAPH_DEFAULT_VIEWS", "RUN_EVIDENCE_GRAPH_VIEW_ORDER"}
    values = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in names}
    assert values["RUN_EVIDENCE_GRAPH_DEFAULT_VIEWS"] == (
        "full_lineage", "failure_path", "resource_authority_path", "closure_path",
    )
    assert values["RUN_EVIDENCE_GRAPH_VIEW_ORDER"] == (
        "full_lineage", "failure_path", "authority", "decision", "resource_authority_path", "closure_path",
    )
