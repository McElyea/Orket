"""Shipped defaults remain authoritative outside the checkout and with CWD impostors."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from orket.runtime.config.contract_assets import CONTRACT_ASSET_ROOT
from orket.runtime.policy.prompt_budget_policy import load_prompt_budget_policy
from orket.runtime.policy.runtime_truth_drift_checker import runtime_truth_contract_drift_report
from orket.runtime.registry.contract_bootstrap import load_runtime_contract_snapshots
from orket.runtime.registry.runtime_invariant_registry import runtime_invariant_registry_snapshot

pytestmark = pytest.mark.integration


def _write_impostors(root: Path):
    for relative in ("artifacts/schema_registry.yaml", "tools/tool_registry.yaml",
                     "tools/compatibility_map.yaml", "tools/compatibility_map_schema.yaml",
                     "policies/prompt_budget.yaml"):
        path = root / "core" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("untrusted: [malformed", encoding="utf-8")


@pytest.mark.asyncio
# Layer: integration
async def test_runtime_defaults_work_in_foreign_cwd_and_ignore_implicit_overrides(tmp_path, monkeypatch):
    assert CONTRACT_ASSET_ROOT.is_absolute()
    monkeypatch.chdir(tmp_path)
    before = await asyncio.to_thread(load_runtime_contract_snapshots)
    budget_before = await asyncio.to_thread(load_prompt_budget_policy)
    assert "workspace.read" in before.tool_registry_snapshot["tools"]
    assert "run_summary.json" in before.artifact_schema_snapshot["artifacts"]
    await asyncio.to_thread(_write_impostors, tmp_path)
    assert await asyncio.to_thread(load_runtime_contract_snapshots) == before
    assert await asyncio.to_thread(load_prompt_budget_policy) == budget_before
    with pytest.raises(ValueError, match="runtime_contract_parse"):
        await asyncio.to_thread(load_runtime_contract_snapshots,
                               artifact_schema_registry_path="core/artifacts/schema_registry.yaml")
    with pytest.raises(ValueError, match="prompt_budget_policy:parse_error"):
        await asyncio.to_thread(load_prompt_budget_policy, "core/policies/prompt_budget.yaml")


@pytest.mark.asyncio
# Layer: integration
async def test_explicit_relative_contract_and_budget_paths_still_select_caller_inputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    registry = {"registry_version": "9.0", "artifacts": {"declared.json": "2.0"}}
    await asyncio.to_thread(Path("registry.yaml").write_text, json.dumps(registry), encoding="utf-8")
    snapshots = await asyncio.to_thread(load_runtime_contract_snapshots, artifact_schema_registry_path="registry.yaml")
    assert snapshots.artifact_schema_snapshot["artifact_versions"] == {"declared.json": "2.0"}
    assert snapshots.artifact_schema_snapshot["artifact_schema_registry_version"] == "9.0"
    policy = await asyncio.to_thread(load_prompt_budget_policy)
    policy["budget_policy_version"] = "9.0"
    policy["stages"]["executor"]["max_tokens"] = 1
    await asyncio.to_thread(Path("budget.yaml").write_text, json.dumps(policy), encoding="utf-8")
    loaded = await asyncio.to_thread(load_prompt_budget_policy, "budget.yaml")
    assert loaded["budget_policy_version"] == "9.0" and loaded["stages"]["executor"]["max_tokens"] == 1
    with pytest.raises(ValueError, match="read_error"):
        await asyncio.to_thread(load_prompt_budget_policy, "missing.yaml")


@pytest.mark.asyncio
# Layer: integration
async def test_invariant_contract_and_startup_drift_gate_ignore_foreign_checkout_docs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    before = await asyncio.to_thread(runtime_invariant_registry_snapshot)
    assert {row["invariant_id"] for row in before["invariants"]} == {f"INV-{i:03d}" for i in range(1, 38)}
    report = await asyncio.to_thread(runtime_truth_contract_drift_report)
    assert report["ok"] is True, [row for row in report["checks"] if not row["ok"]]
    doc = tmp_path / "docs/specs/RUNTIME_INVARIANTS.md"
    await asyncio.to_thread(doc.parent.mkdir, parents=True)
    await asyncio.to_thread(doc.write_text, "# No admitted invariants here\n", encoding="utf-8")
    assert await asyncio.to_thread(runtime_invariant_registry_snapshot) == before
    with pytest.raises(ValueError, match="E_RUNTIME_INVARIANT_REGISTRY_EMPTY"):
        await asyncio.to_thread(runtime_invariant_registry_snapshot, doc_path=doc)
