from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, FrozenSet, Iterable, Set, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = PROJECT_ROOT / "model" / "core" / "contracts" / "dependency_direction_policy.json"


@dataclass(frozen=True)
class DependencyPolicy:
    schema_version: str
    policy_id: str
    scan_roots: Tuple[str, ...]
    top_level_to_layer: Dict[str, str]
    forbidden_edges: FrozenSet[Tuple[str, str]]
    legacy_edge_budget_max: int | None

    def layer_for_module(self, module: str) -> str:
        if not module.startswith("orket."):
            return "external"
        parts = module.split(".")
        if len(parts) < 2:
            raise ValueError(f"Invalid local module path: {module}")
        top_level = parts[1]
        try:
            return self.top_level_to_layer[top_level]
        except KeyError as exc:
            raise ValueError(f"Unknown top-level namespace in dependency policy: {top_level}") from exc


def _parse_forbidden_edges(edges: Iterable[dict]) -> FrozenSet[Tuple[str, str]]:
    parsed: Set[Tuple[str, str]] = set()
    for edge in edges:
        src = edge.get("source_layer")
        dst = edge.get("target_layer")
        if not isinstance(src, str) or not isinstance(dst, str):
            raise ValueError("dependency policy forbidden_edges entries must include string source_layer/target_layer")
        parsed.add((src, dst))
    return frozenset(parsed)


def load_dependency_policy(path: Path = POLICY_PATH) -> DependencyPolicy:
    payload = json.loads(path.read_text(encoding="utf-8"))
    scan_roots = payload.get("scan_roots", [])
    mapping = payload.get("top_level_to_layer", {})
    if not isinstance(scan_roots, list) or not all(isinstance(v, str) for v in scan_roots):
        raise ValueError("dependency policy scan_roots must be a list[str]")
    if not isinstance(mapping, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()):
        raise ValueError("dependency policy top_level_to_layer must be a dict[str, str]")
    legacy_budget_raw = payload.get("legacy_edge_budget")
    legacy_budget = None
    if isinstance(legacy_budget_raw, dict) and legacy_budget_raw.get("max_edges") is not None:
        legacy_budget = int(legacy_budget_raw["max_edges"])

    return DependencyPolicy(
        schema_version=str(payload.get("schema_version", "")),
        policy_id=str(payload.get("policy_id", "")),
        scan_roots=tuple(scan_roots),
        top_level_to_layer=mapping,
        forbidden_edges=_parse_forbidden_edges(payload.get("forbidden_edges", [])),
        legacy_edge_budget_max=legacy_budget,
    )
