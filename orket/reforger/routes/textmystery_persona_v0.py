from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None

ROUTE_ID_TEXTMYSTERY_PERSONA_V0 = "textmystery_persona_v0"


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


class TextMysteryPersonaRouteV0:
    route_id = ROUTE_ID_TEXTMYSTERY_PERSONA_V0
    expected_inputs = (
        "content/prompts/archetypes.yaml",
        "content/prompts/npcs.yaml",
        "content/refusal_styles.yaml",
    )

    def inspect(self, input_dir: Path) -> RoutePlan:
        if yaml is None:
            return RoutePlan(
                route_id=self.route_id,
                expected_inputs=self.expected_inputs,
                found_inputs=(),
                missing_inputs=self.expected_inputs,
                errors=("PyYAML unavailable",),
                warnings=(),
            )
        found: list[str] = []
        missing: list[str] = []
        errors: list[str] = []
        warnings: list[str] = []

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
            warnings=tuple(sorted(warnings)),
        )

    def normalize(self, input_dir: Path) -> dict[str, Any]:
        if yaml is None:
            raise ValueError("PyYAML unavailable")
        archetypes = self._load_yaml(input_dir / "content" / "prompts" / "archetypes.yaml")
        npcs = self._load_yaml(input_dir / "content" / "prompts" / "npcs.yaml")
        refusal_styles = self._load_yaml(input_dir / "content" / "refusal_styles.yaml")

        defaults = archetypes.get("defaults") if isinstance(archetypes, dict) else {}
        arche_map = archetypes.get("archetypes") if isinstance(archetypes, dict) else {}
        npc_map = npcs.get("npcs") if isinstance(npcs, dict) else {}
        if not isinstance(defaults, dict):
            defaults = {}
        if not isinstance(arche_map, dict):
            arche_map = {}
        if not isinstance(npc_map, dict):
            npc_map = {}

        style_map: dict[str, dict[str, Any]] = {}
        if isinstance(refusal_styles, list):
            for item in refusal_styles:
                if not isinstance(item, dict):
                    continue
                style_id = str(item.get("id") or "").strip()
                if not style_id:
                    continue
                templates = item.get("templates")
                if isinstance(templates, list):
                    cleaned = [str(t).strip() for t in templates if str(t).strip()]
                else:
                    cleaned = []
                style_map[style_id] = {"templates": cleaned}

        canonical = {
            "version": "persona_blob.v0",
            "route_id": self.route_id,
            "banks": {
                "archetypes": self._normalize_archetypes(arche_map),
                "refusal_styles": {key: style_map[key] for key in sorted(style_map)},
            },
            "entities": {
                "npcs": self._normalize_npcs(npc_map),
            },
            "rules": {
                "defaults": self._normalize_object(defaults),
                "mode": "truth_only",
            },
            "serialization": {
                "map_sort": "lexicographic",
                "list_order_policy": {
                    "refusal_styles.templates": "preserve",
                    "archetypes.banks.*": "preserve",
                },
            },
        }
        self.validate_blob(canonical)
        return canonical

    def materialize(self, blob: dict[str, Any], out_dir: Path) -> tuple[str, ...]:
        self.validate_blob(blob)
        if yaml is None:
            raise ValueError("PyYAML unavailable")
        outputs: list[str] = []
        content = out_dir / "content"
        prompts = content / "prompts"
        prompts.mkdir(parents=True, exist_ok=True)

        arche_payload = {
            "version": 1,
            "defaults": blob["rules"]["defaults"],
            "archetypes": blob["banks"]["archetypes"],
        }
        arche_path = prompts / "archetypes.yaml"
        arche_path.write_text(yaml.safe_dump(arche_payload, sort_keys=True), encoding="utf-8")
        outputs.append(str(arche_path.relative_to(out_dir)).replace("\\", "/"))

        npcs_payload = {
            "version": 1,
            "npcs": blob["entities"]["npcs"],
        }
        npcs_path = prompts / "npcs.yaml"
        npcs_path.write_text(yaml.safe_dump(npcs_payload, sort_keys=True), encoding="utf-8")
        outputs.append(str(npcs_path.relative_to(out_dir)).replace("\\", "/"))

        styles_rows: list[dict[str, Any]] = []
        for style_id in sorted(blob["banks"]["refusal_styles"]):
            item = blob["banks"]["refusal_styles"][style_id]
            styles_rows.append({"id": style_id, "templates": list(item.get("templates", []))})
        style_path = content / "refusal_styles.yaml"
        style_path.write_text(yaml.safe_dump(styles_rows, sort_keys=True), encoding="utf-8")
        outputs.append(str(style_path.relative_to(out_dir)).replace("\\", "/"))
        return tuple(sorted(outputs))

    def validate_blob(self, blob: dict[str, Any]) -> None:
        if not isinstance(blob, dict):
            raise ValueError("blob must be an object")
        if blob.get("version") != "persona_blob.v0":
            raise ValueError("blob.version must be persona_blob.v0")
        banks = blob.get("banks")
        entities = blob.get("entities")
        rules = blob.get("rules")
        if not isinstance(banks, dict) or not isinstance(entities, dict) or not isinstance(rules, dict):
            raise ValueError("blob missing banks/entities/rules objects")
        archetypes = banks.get("archetypes")
        refusal_styles = banks.get("refusal_styles")
        npcs = entities.get("npcs")
        if not isinstance(archetypes, dict) or not isinstance(refusal_styles, dict) or not isinstance(npcs, dict):
            raise ValueError("blob missing archetypes/refusal_styles/npcs objects")

        for npc_id in sorted(npcs):
            npc = npcs[npc_id]
            if not isinstance(npc, dict):
                raise ValueError(f"npc '{npc_id}' must be object")
            archetype = str(npc.get("archetype") or "").strip()
            if not archetype or archetype not in archetypes:
                raise ValueError(f"npc '{npc_id}' references unknown archetype '{archetype}'")
            style_id = str(npc.get("refusal_style_id") or "").strip()
            if style_id and style_id not in refusal_styles:
                raise ValueError(f"npc '{npc_id}' references unknown refusal_style_id '{style_id}'")

    @staticmethod
    def canonical_json(blob: dict[str, Any]) -> str:
        return json.dumps(blob, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    @staticmethod
    def _load_yaml(path: Path) -> Any:
        if yaml is None:
            raise ValueError("PyYAML unavailable")
        if not path.is_file():
            raise ValueError(f"missing input file: {path}")
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"invalid yaml: {path}") from exc
        return payload

    def _normalize_archetypes(self, archetypes: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for aid in sorted(archetypes):
            value = archetypes[aid]
            if not isinstance(value, dict):
                continue
            result[aid] = self._normalize_object(value)
        return result

    def _normalize_npcs(self, npcs: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for nid in sorted(npcs):
            value = npcs[nid]
            if not isinstance(value, dict):
                continue
            result[nid] = self._normalize_object(value)
        return result

    def _normalize_object(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): self._normalize_object(value[k]) for k in sorted(value)}
        if isinstance(value, list):
            return [self._normalize_object(item) for item in value]
        return value

