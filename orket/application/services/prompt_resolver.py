from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Dict, List, Optional

from orket.application.services.prompt_compiler import PromptCompiler
from orket.schema import DialectConfig, SkillConfig


@dataclass
class PromptResolution:
    system_prompt: str
    metadata: Dict[str, Any]
    layers: Dict[str, Any]


class PromptResolver:
    """
    Deterministic prompt resolver for role+dialect+policy context composition.

    Precedence order:
    role/base -> dialect adapter -> guards -> context overlays
    """
    ALLOWED_GUARDS = {"hallucination", "security", "consistency"}
    GUARD_PROMPT_OVERLAYS = {
        "hallucination": [
            "Do not invent facts, APIs, files, or system behavior.",
            "Do not assume details not explicitly provided.",
            "If information is missing, state that it is missing.",
            "If you reference context, cite the exact part you used.",
            "If unsure, ask for clarification instead of guessing.",
        ],
        "security": [
            "Do not propose unsafe actions, secret exposure, or unapproved data exfiltration.",
            "Respect workspace and tool authorization boundaries.",
        ],
        "consistency": [
            "Follow required output format and schema contracts exactly.",
            "Do not contradict provided context or declared constraints.",
        ],
    }

    @staticmethod
    def resolve(
        *,
        skill: SkillConfig,
        dialect: DialectConfig,
        context: Optional[Dict[str, Any]] = None,
        guards: Optional[List[str]] = None,
        version_hint: str = "stable",
        selection_policy: str = "stable",
        next_member: Optional[str] = None,
        patch: Optional[str] = None,
    ) -> PromptResolution:
        context = context or {}
        guards = PromptResolver._normalize_guard_layers(guards or [])

        base_prompt = PromptCompiler.compile(
            skill=skill,
            dialect=dialect,
            next_member=next_member,
            patch=patch,
        )

        role_meta = dict(getattr(skill, "prompt_metadata", {}) or {})
        if not role_meta:
            role_meta = dict(getattr(skill, "capabilities", {}) or {}).get("prompt_metadata", {})
        dialect_meta = dict(getattr(dialect, "prompt_metadata", {}) or {})

        dialect_prefix = str(getattr(dialect, "system_prefix", "") or "").strip()
        guard_lines = PromptResolver._guard_lines(guards)
        context_lines = PromptResolver._context_overlay_lines(context)

        prompt_parts: List[str] = []
        if dialect_prefix:
            prompt_parts.append(dialect_prefix)
        prompt_parts.append(base_prompt)
        if guard_lines:
            prompt_parts.append("PROMPT GUARD OVERLAYS:\n" + "\n".join(guard_lines))
        if context_lines:
            prompt_parts.append("PROMPT CONTEXT OVERLAYS:\n" + "\n".join(context_lines))
        final_prompt = "\n\n".join([part for part in prompt_parts if part.strip()])

        checksum = PromptResolver._checksum(final_prompt)
        role_name = str(skill.name or "").strip().lower()
        dialect_name = str(dialect.model_family or "").strip().lower()
        role_version = str(role_meta.get("version") or "1.0.0")
        dialect_version = str(dialect_meta.get("version") or "1.0.0")
        resolver_policy = str(context.get("prompt_resolver_policy") or "resolver_v1")
        role_status = str(role_meta.get("status") or "draft").strip().lower()
        dialect_status = str(dialect_meta.get("status") or "draft").strip().lower()
        resolved_selection_policy = str(
            context.get("prompt_selection_policy") or selection_policy
        ).strip().lower()
        PromptResolver._validate_selection_policy(
            policy=resolved_selection_policy,
            role_status=role_status,
            dialect_status=dialect_status,
            role_version=role_version,
            dialect_version=dialect_version,
            context=context,
        )
        PromptResolver._validate_rule_ownership(context=context)

        metadata = {
            "prompt_id": f"role.{role_name}+dialect.{dialect_name}",
            "prompt_version": f"{role_version}/{dialect_version}",
            "prompt_checksum": checksum,
            "resolver_policy": resolver_policy,
            "version_hint": version_hint,
            "selection_policy": resolved_selection_policy,
            "role_status": role_status,
            "dialect_status": dialect_status,
            "role": role_name,
            "dialect": dialect_name,
            "guard_count": len(guards),
        }
        layers = {
            "role_base": {
                "name": role_name,
                "version": role_version,
            },
            "dialect_adapter": {
                "name": dialect_name,
                "version": dialect_version,
                "prefix_applied": bool(dialect_prefix),
            },
            "guards": guards,
            "context_profile": str(context.get("prompt_context_profile") or "default"),
        }
        return PromptResolution(system_prompt=final_prompt, metadata=metadata, layers=layers)

    @staticmethod
    def _guard_lines(guards: List[str]) -> List[str]:
        lines = []
        for guard in guards:
            normalized = str(guard).strip()
            if not normalized:
                continue
            overlays = PromptResolver.GUARD_PROMPT_OVERLAYS.get(normalized.lower(), [])
            if not overlays:
                lines.append(f"- [{normalized}]")
                continue
            lines.append(f"- [{normalized}]")
            for instruction in overlays:
                lines.append(f"  - {instruction}")
        return lines

    @staticmethod
    def _normalize_guard_layers(guards: List[str]) -> List[str]:
        normalized_guards: List[str] = []
        seen = set()
        for guard in guards:
            normalized = str(guard).strip().lower()
            if not normalized:
                continue
            if normalized not in PromptResolver.ALLOWED_GUARDS:
                raise ValueError(
                    f"Unsupported guard layer '{normalized}'. "
                    f"Allowed: {', '.join(sorted(PromptResolver.ALLOWED_GUARDS))}"
                )
            if normalized in seen:
                continue
            seen.add(normalized)
            normalized_guards.append(normalized)
        return normalized_guards

    @staticmethod
    def _context_overlay_lines(context: Dict[str, Any]) -> List[str]:
        keys = (
            "prompt_context_profile",
            "stage_gate_mode",
            "required_action_tools",
            "required_statuses",
            "required_read_paths",
            "required_write_paths",
        )
        lines: List[str] = []
        for key in keys:
            if key not in context:
                continue
            value = context.get(key)
            if value is None:
                continue
            if isinstance(value, (dict, list)):
                rendered = json.dumps(value, sort_keys=True)
            else:
                rendered = str(value)
            lines.append(f"- {key}: {rendered}")
        return lines

    @staticmethod
    def _checksum(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _validate_selection_policy(
        *,
        policy: str,
        role_status: str,
        dialect_status: str,
        role_version: str,
        dialect_version: str,
        context: Dict[str, Any],
    ) -> None:
        allowed = {"stable", "canary", "exact"}
        if policy not in allowed:
            raise ValueError(f"Unsupported prompt selection policy: {policy}")

        strict = bool(context.get("prompt_selection_strict", False))
        if policy == "stable":
            if strict and (role_status != "stable" or dialect_status != "stable"):
                raise ValueError(
                    f"Stable policy requires stable assets (role={role_status}, dialect={dialect_status})"
                )
            return

        if policy == "canary":
            canary_allowed = {"stable", "candidate", "canary"}
            if strict and (role_status not in canary_allowed or dialect_status not in canary_allowed):
                raise ValueError(
                    f"Canary policy requires candidate/canary/stable assets (role={role_status}, dialect={dialect_status})"
                )
            return

        exact = str(context.get("prompt_version_exact") or "").strip()
        if not exact:
            if strict:
                raise ValueError("Exact policy requires prompt_version_exact in context")
            return
        resolved = f"{role_version}/{dialect_version}"
        if strict and exact != resolved:
            raise ValueError(f"Exact policy version mismatch: expected {exact}, resolved {resolved}")

    @staticmethod
    def _normalize_rule_ids(value: Any) -> List[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        normalized: List[str] = []
        seen = set()
        for item in value:
            rule_id = str(item or "").strip()
            if not rule_id:
                continue
            if rule_id in seen:
                continue
            seen.add(rule_id)
            normalized.append(rule_id)
        return normalized

    @staticmethod
    def _validate_rule_ownership(*, context: Dict[str, Any]) -> None:
        prompt_rule_ids = PromptResolver._normalize_rule_ids(context.get("prompt_rule_ids"))
        runtime_guard_rule_ids = PromptResolver._normalize_rule_ids(context.get("runtime_guard_rule_ids"))
        if not prompt_rule_ids or not runtime_guard_rule_ids:
            return
        overlap = sorted(set(prompt_rule_ids).intersection(runtime_guard_rule_ids))
        if overlap:
            raise ValueError(
                "Rule ownership conflict between prompt and runtime guard catalogs: "
                + ", ".join(overlap)
            )
