"""Locations of the single shipped copy of runtime contracts and policies."""
from __future__ import annotations

from pathlib import Path

# Wheels install these immutable defaults beside this module; CWD is not authority.
CONTRACT_ASSET_ROOT = Path(__file__).parent / "assets"
DEFAULT_ARTIFACT_SCHEMA_REGISTRY_PATH = CONTRACT_ASSET_ROOT / "artifacts/schema_registry.yaml"
DEFAULT_COMPATIBILITY_MAP_PATH = CONTRACT_ASSET_ROOT / "tools/compatibility_map.yaml"
DEFAULT_COMPATIBILITY_MAP_SCHEMA_PATH = CONTRACT_ASSET_ROOT / "tools/compatibility_map_schema.yaml"
DEFAULT_TOOL_REGISTRY_PATH = CONTRACT_ASSET_ROOT / "tools/tool_registry.yaml"
DEFAULT_PROMPT_BUDGET_PATH = CONTRACT_ASSET_ROOT / "policies/prompt_budget.yaml"
ARTIFACT_RETENTION_TIERS_PATH = CONTRACT_ASSET_ROOT / "policies/artifact_retention_tiers.yaml"
RUN_SUMMARY_SCHEMA_PATH = CONTRACT_ASSET_ROOT / "artifacts/run_summary_schema.json"
RUN_GRAPH_SCHEMA_PATH = CONTRACT_ASSET_ROOT / "artifacts/run_graph_schema.json"
RUN_EVIDENCE_GRAPH_SCHEMA_PATH = CONTRACT_ASSET_ROOT / "artifacts/run_evidence_graph_schema.json"
DEFAULT_RUNTIME_INVARIANTS_DOC_PATH = CONTRACT_ASSET_ROOT / "contracts/RUNTIME_INVARIANTS.md"
