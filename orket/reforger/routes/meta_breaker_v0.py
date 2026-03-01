from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROUTE_ID_META_BREAKER_V0 = "meta_breaker_v0"


@dataclass(frozen=True)
class RoutePlan:
    route_id: str
    expected_inputs: tuple[str, ...]
    found_inputs: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.missing_inputs and not self.errors


class MetaBreakerRouteV0:
    route_id = ROUTE_ID_META_BREAKER_V0
    expected_inputs = ("rules/meta_breaker_rules.json",)

    def inspect(self, input_dir: Path) -> RoutePlan:
        found: list[str] = []
        missing: list[str] = []
        errors: list[str] = []

        for rel in self.expected_inputs:
            path = input_dir / rel
            if path.is_file():
                found.append(rel)
            else:
                missing.append(rel)

        if not missing:
            try:
                blob = self.normalize(input_dir)
                self.validate_blob(blob)
            except ValueError as exc:
                errors.append(str(exc))

        return RoutePlan(
            route_id=self.route_id,
            expected_inputs=self.expected_inputs,
            found_inputs=tuple(sorted(found)),
            missing_inputs=tuple(sorted(missing)),
            errors=tuple(sorted(errors)),
            warnings=(),
        )

    def normalize(self, input_dir: Path) -> dict[str, Any]:
        rules_path = input_dir / "rules" / "meta_breaker_rules.json"
        if not rules_path.is_file():
            raise ValueError(f"missing input file: {rules_path}")
        payload = json.loads(rules_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("meta_breaker_rules.json must be an object")
        archetypes = payload.get("archetypes")
        balance = payload.get("balance")
        if not isinstance(archetypes, dict):
            raise ValueError("archetypes must be an object")
        if not isinstance(balance, dict):
            raise ValueError("balance must be an object")
        canonical = {
            "version": "meta_breaker_blob.v0",
            "route_id": self.route_id,
            "archetypes": self._normalize_object(archetypes),
            "balance": self._normalize_object(balance),
            "serialization": {"map_sort": "lexicographic"},
        }
        self.validate_blob(canonical)
        return canonical

    def materialize(self, blob: dict[str, Any], out_dir: Path) -> tuple[str, ...]:
        self.validate_blob(blob)
        rules_path = out_dir / "rules" / "meta_breaker_rules.json"
        rules_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "archetypes": blob["archetypes"],
            "balance": blob["balance"],
        }
        rules_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return ("rules/meta_breaker_rules.json",)

    def validate_blob(self, blob: dict[str, Any]) -> None:
        if not isinstance(blob, dict):
            raise ValueError("blob must be an object")
        if blob.get("version") != "meta_breaker_blob.v0":
            raise ValueError("blob.version must be meta_breaker_blob.v0")
        archetypes = blob.get("archetypes")
        balance = blob.get("balance")
        if not isinstance(archetypes, dict) or not isinstance(balance, dict):
            raise ValueError("blob missing archetypes/balance objects")
        arche_ids = sorted(archetypes.keys())
        if len(arche_ids) < 2:
            raise ValueError("meta breaker requires at least two archetypes")
        first_player_advantage = float(balance.get("first_player_advantage", 0.0))
        if first_player_advantage < 0.0 or first_player_advantage > 0.2:
            raise ValueError("balance.first_player_advantage out of range")
        dominant_threshold = float(balance.get("dominant_threshold", 0.55))
        if dominant_threshold < 0.45 or dominant_threshold > 0.9:
            raise ValueError("balance.dominant_threshold out of range")
        for left in arche_ids:
            row = archetypes[left]
            if not isinstance(row, dict):
                raise ValueError(f"archetype '{left}' must be object")
            vs = row.get("vs")
            if not isinstance(vs, dict):
                raise ValueError(f"archetype '{left}'.vs must be object")
            for right in arche_ids:
                if right not in vs:
                    raise ValueError(f"missing matchup cell: {left}.vs.{right}")
                value = float(vs[right])
                if value < 0.0 or value > 1.0:
                    raise ValueError(f"matchup value out of range: {left}.vs.{right}")

    @staticmethod
    def canonical_json(blob: dict[str, Any]) -> str:
        return json.dumps(blob, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def _normalize_object(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): self._normalize_object(value[k]) for k in sorted(value)}
        if isinstance(value, list):
            return [self._normalize_object(item) for item in value]
        return value
