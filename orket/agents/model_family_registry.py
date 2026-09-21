from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

MODEL_FAMILY_PATTERNS_ENV = "ORKET_MODEL_FAMILY_PATTERNS"


@dataclass(frozen=True)
class ModelFamilyPattern:
    pattern: str
    family: str


@dataclass(frozen=True)
class ModelFamilyMatch:
    family: str
    recognized: bool


DEFAULT_MODEL_FAMILY_PATTERNS = (
    ModelFamilyPattern("deepseek", "deepseek-r1"),
    ModelFamilyPattern("llama", "llama3"),
    ModelFamilyPattern("phi", "phi"),
    ModelFamilyPattern("qwen", "qwen"),
)


class ModelFamilyRegistry:
    def __init__(self, patterns: tuple[ModelFamilyPattern, ...] = DEFAULT_MODEL_FAMILY_PATTERNS) -> None:
        self.patterns = patterns

    @classmethod
    def from_config(cls, config: Any | None = None) -> ModelFamilyRegistry:
        patterns = _parse_patterns(config)
        if not patterns:
            return cls()
        return cls((*patterns, *DEFAULT_MODEL_FAMILY_PATTERNS))

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> ModelFamilyRegistry:
        raw = environment.get(MODEL_FAMILY_PATTERNS_ENV, "").strip()
        if not raw:
            return cls()
        try:
            config = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("E_MODEL_FAMILY_PATTERNS_JSON") from exc
        return cls.from_config(config)

    def resolve(self, model_name: str) -> ModelFamilyMatch:
        normalized = str(model_name or "").strip().lower()
        for entry in self.patterns:
            pattern = entry.pattern.strip().lower()
            if pattern and pattern in normalized:
                return ModelFamilyMatch(family=entry.family, recognized=True)
        return ModelFamilyMatch(family="generic", recognized=False)


def _parse_patterns(config: Any) -> tuple[ModelFamilyPattern, ...]:
    if isinstance(config, dict):
        items = [{"pattern": key, "family": value} for key, value in config.items()]
    elif isinstance(config, list):
        items = config
    else:
        return ()

    patterns: list[ModelFamilyPattern] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        pattern = str(item.get("pattern") or item.get("contains") or "").strip()
        family = str(item.get("family") or item.get("model_family") or "").strip()
        if pattern and family:
            patterns.append(ModelFamilyPattern(pattern=pattern, family=family))
    return tuple(patterns)
