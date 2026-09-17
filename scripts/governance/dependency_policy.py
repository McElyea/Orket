"""Five-layer dependency policy for standalone repository tooling."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import MappingProxyType

PROJECT_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = PROJECT_ROOT / "model/core/contracts/dependency_direction_policy.json"
LAYERS = frozenset({"core", "application", "adapters", "interfaces", "decision_nodes"})
MODULE = re.compile(r"orket(?:\.[A-Za-z_]\w*)+\Z")


@dataclass(frozen=True)
class EdgeException:
    id: str
    source: str
    target: str
    owner: str
    reason: str
    introduced: str
    removal: str
    expires: str | None = None


@dataclass(frozen=True)
class DependencyPolicy:
    schema_version: str
    policy_id: str
    scan_roots: tuple[str, ...]
    classifications: Mapping[str, str]
    allowed_edges: frozenset[tuple[str, str]]
    decision_core_contracts: frozenset[str]
    side_effect_free_adapters: frozenset[str]
    exceptions: tuple[EdgeException, ...]
    source_sha256: str
    source_document: str

    def layer_for_module(self, module: str) -> str:
        matches = [p for p in self.classifications if module == p or module.startswith(p + ".")]
        if not matches:
            raise ValueError(f"Unclassified repository module: {module}")
        return self.classifications[max(matches, key=len)]

    def permits(self, source: str, target: str) -> bool:
        left, right = self.layer_for_module(source), self.layer_for_module(target)
        if left == "decision_nodes" and right == "adapters":
            return target in self.side_effect_free_adapters
        if (left, right) not in self.allowed_edges:
            return False
        if left == "decision_nodes" and right == "core":
            return target in self.decision_core_contracts
        return True


def _module_set(payload: dict, key: str) -> frozenset[str]:
    values = payload[key]
    if not isinstance(values, list) or any(not isinstance(n, str) or not MODULE.fullmatch(n) for n in values):
        raise ValueError(f"{key} must contain exact repository module names")
    if len(set(values)) != len(values):
        raise ValueError(f"Duplicate module in {key}")
    return frozenset(values)


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate dependency policy key: {key}")
        result[key] = value
    return result


def _exceptions(rows: object, today: date) -> tuple[EdgeException, ...]:
    if not isinstance(rows, list):
        raise ValueError("exceptions must be a list")
    seen_ids, seen_edges, result = set(), set(), []
    required = {"id", "source", "target", "owner", "reason", "introduced", "removal"}
    for row in rows:
        if not isinstance(row, dict) or not required <= row.keys() or row.keys() - required - {"expires"}:
            raise ValueError("Exception requires exact source/target, owner, reason, introduction and removal")
        if any(not isinstance(row[k], str) or not row[k].strip() for k in required):
            raise ValueError("Exception fields must be nonempty strings")
        if any(not MODULE.fullmatch(row[k]) for k in ("source", "target")):
            raise ValueError("Exception source and target must be exact module names")
        if date.fromisoformat(row["introduced"]) > today:
            raise ValueError(f"Future exception introduction: {row['id']}")
        if row.get("expires") is not None and date.fromisoformat(row["expires"]) <= today:
            raise ValueError(f"Expired exception: {row['id']}")
        edge = row["source"], row["target"]
        if row["id"] in seen_ids or edge in seen_edges:
            raise ValueError("Duplicate exception identity or edge")
        seen_ids.add(row["id"])
        seen_edges.add(edge)
        result.append(EdgeException(**row))
    return tuple(result)


def load_dependency_policy(path: Path = POLICY_PATH, *, today: date | None = None) -> DependencyPolicy:
    raw = path.read_bytes()
    document = raw.decode("utf-8")
    payload = json.loads(document, object_pairs_hook=_unique_object)
    required = {
        "schema_version",
        "policy_id",
        "scan_roots",
        "classifications",
        "allowed_edges",
        "decision_core_contracts",
        "side_effect_free_adapters",
        "exceptions",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError("Dependency policy v2 requires exactly the declared policy fields")
    if payload["schema_version"] != "2.0.0" or payload["policy_id"] != "dependency_direction_policy":
        raise ValueError("Unsupported dependency policy identity/version")
    if payload["scan_roots"] != ["orket"]:
        raise ValueError("Dependency policy must scan the complete orket package")
    mapping = payload["classifications"]
    if (
        not isinstance(mapping, dict)
        or not mapping
        or any(not isinstance(k, str) or not MODULE.fullmatch(k) or v not in LAYERS for k, v in mapping.items())
    ):
        raise ValueError("Classifications must map module prefixes to the five normative layers")
    rows = payload["allowed_edges"]
    if not isinstance(rows, list) or any(
        not isinstance(e, list) or len(e) != 2 or any(n not in LAYERS for n in e) for e in rows
    ):
        raise ValueError("Allowed edges must be pairs of normative layers")
    edges = frozenset(tuple(e) for e in rows)
    if len(edges) != len(rows):
        raise ValueError("Duplicate allowed edge")
    policy = DependencyPolicy(
        "2.0.0",
        payload["policy_id"],
        ("orket",),
        MappingProxyType(dict(mapping)),
        edges,
        _module_set(payload, "decision_core_contracts"),
        _module_set(payload, "side_effect_free_adapters"),
        _exceptions(payload["exceptions"], today or date.today()),
        hashlib.sha256(raw).hexdigest(),
        document,
    )
    for names, layer in ((policy.decision_core_contracts, "core"), (policy.side_effect_free_adapters, "adapters")):
        if any(policy.layer_for_module(n) != layer for n in names):
            raise ValueError(f"Declared {layer} targets have a conflicting classification")
    return policy
