from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from typing import Any

from orket.application.services.skill_adapter import synthesize_role_tool_profile_bindings
from orket.core.domain.guard_rule_catalog import resolve_runtime_guard_rule_ids
from orket.runtime.truthful_memory_policy import render_reference_context_rows
from orket.schema import DialectConfig, SkillConfig


class OrchestratorPromptPreparationService:
    """Owns prompt compilation or resolution and final turn-context assembly."""

    def __init__(
        self,
        *,
        organization: Any,
        memory: Any,
        support_services: Any,
        build_turn_context: Callable[..., dict[str, Any]],
        resolve_prompt_resolver_mode: Callable[[], str],
        resolve_prompt_selection_policy: Callable[[], str],
        resolve_prompt_selection_strict: Callable[[], bool],
        resolve_prompt_version_exact: Callable[[], str],
        resolve_prompt_patch: Callable[[], str],
        resolve_prompt_patch_label: Callable[[], str],
        should_suppress_reference_context_for_cards_runtime: Callable[[dict[str, Any] | None], bool],
        load_asset: Callable[[str, str, Any], Awaitable[Any]],
    ) -> None:
        self.organization = organization
        self.memory = memory
        self.support_services = support_services
        self.build_turn_context = build_turn_context
        self.resolve_prompt_resolver_mode = resolve_prompt_resolver_mode
        self.resolve_prompt_selection_policy = resolve_prompt_selection_policy
        self.resolve_prompt_selection_strict = resolve_prompt_selection_strict
        self.resolve_prompt_version_exact = resolve_prompt_version_exact
        self.resolve_prompt_patch = resolve_prompt_patch
        self.resolve_prompt_patch_label = resolve_prompt_patch_label
        self.should_suppress_reference_context_for_cards_runtime = (
            should_suppress_reference_context_for_cards_runtime
        )
        self.load_asset = load_asset

    async def build(
        self,
        *,
        issue: Any,
        epic: Any,
        prompt_strategy_node: Any,
        run_id: str,
        seat_name: str,
        roles_to_load: list[str],
        turn_status: Any,
        selected_model: str,
        dependency_context: dict[str, Any],
        runtime_result: Any | None,
        resume_mode: bool,
        cards_runtime: dict[str, Any],
        role_config: Any,
    ) -> tuple[dict[str, Any], str]:
        dialect_name = prompt_strategy_node.select_dialect(selected_model)
        dialect = await self.load_asset("dialects", dialect_name, DialectConfig)
        skill = SkillConfig(
            name=role_config.name or seat_name,
            intent=role_config.description,
            responsibilities=[ro.description for ro in [role_config]],
            tools=role_config.tools,
            prompt_metadata=dict(getattr(role_config, "prompt_metadata", {}) or {}),
        )
        skill_tool_bindings = synthesize_role_tool_profile_bindings(role_config.tools)
        search_query = (issue.name or "") + " " + (issue.note or "")
        memories = await self.memory.search(search_query.strip())
        memory_context = render_reference_context_rows(memories)

        prompt_mode = self.resolve_prompt_resolver_mode()
        selection_policy = self.resolve_prompt_selection_policy()
        selection_strict = self.resolve_prompt_selection_strict()
        exact_version = self.resolve_prompt_version_exact()
        prompt_patch = self.resolve_prompt_patch()
        prompt_patch_label = self.resolve_prompt_patch_label()
        architecture_governance = getattr(epic, "architecture_governance", None)
        idesign_enabled = bool(getattr(architecture_governance, "idesign", False))
        if not isinstance(getattr(issue, "params", None), dict):
            issue.params = {}
        issue.params["idesign_enabled"] = idesign_enabled
        provisional_context = self.build_turn_context(
            run_id=run_id,
            issue=issue,
            seat_name=seat_name,
            roles_to_load=roles_to_load,
            turn_status=turn_status,
            selected_model=selected_model,
            dependency_context=dependency_context,
            runtime_verifier_ok=(None if runtime_result is None else bool(runtime_result.ok)),
            prompt_metadata={},
            prompt_layers={},
            idesign_enabled=idesign_enabled,
            resume_mode=resume_mode,
            skill_tool_bindings=skill_tool_bindings,
            cards_runtime=cards_runtime,
        )
        prompt_metadata: dict[str, Any] = {
            "prompt_id": "legacy.prompt_compiler",
            "prompt_version": "legacy",
            "prompt_checksum": "",
            "resolver_policy": "compiler",
            "selection_policy": selection_policy,
            "role_status": "legacy",
            "dialect_status": "legacy",
        }
        prompt_layers: dict[str, Any] = {
            "role_base": {"name": str(skill.name or "").strip().lower(), "version": "legacy"},
            "dialect_adapter": {"name": str(dialect.model_family or "").strip().lower(), "version": "legacy"},
            "guards": [],
            "context_profile": "default",
        }
        if prompt_mode == "resolver":
            role_rule_ids = list((getattr(role_config, "prompt_metadata", {}) or {}).get("owned_rule_ids", []) or [])
            dialect_rule_ids = list((getattr(dialect, "prompt_metadata", {}) or {}).get("owned_rule_ids", []) or [])
            runtime_guard_rule_ids: list[str] = resolve_runtime_guard_rule_ids(None)
            guard_layers: list[str] = ["hallucination"]
            if self.organization and isinstance(getattr(self.organization, "process_rules", None), dict):
                configured_rule_ids = self.organization.process_rules.get("runtime_guard_rule_ids")
                if isinstance(configured_rule_ids, list):
                    runtime_guard_rule_ids = resolve_runtime_guard_rule_ids(configured_rule_ids)
                configured_layers = self.organization.process_rules.get("prompt_guard_layers")
                if isinstance(configured_layers, list) and configured_layers:
                    guard_layers = [str(item) for item in configured_layers if str(item).strip()]
            resolution = self.support_services.resolve_prompt(
                skill=skill,
                dialect=dialect,
                context={
                    "prompt_context_profile": "long_project" if memory_context else "default",
                    "prompt_resolver_policy": "resolver_v1",
                    "prompt_selection_policy": selection_policy,
                    "prompt_selection_strict": selection_strict,
                    "prompt_version_exact": exact_version,
                    "stage_gate_mode": provisional_context.get("stage_gate_mode"),
                    "required_action_tools": provisional_context.get("required_action_tools", []),
                    "required_statuses": provisional_context.get("required_statuses", []),
                    "required_read_paths": provisional_context.get("required_read_paths", []),
                    "required_write_paths": provisional_context.get("required_write_paths", []),
                    "protocol_governed_enabled": provisional_context.get("protocol_governed_enabled", False),
                    "prompt_rule_ids": role_rule_ids + dialect_rule_ids,
                    "runtime_guard_rule_ids": runtime_guard_rule_ids,
                },
                guards=guard_layers,
                selection_policy=selection_policy,
                patch=(prompt_patch or None),
            )
            system_prompt = resolution.system_prompt
            prompt_metadata = dict(resolution.metadata)
            prompt_layers = dict(resolution.layers)
        else:
            system_prompt = self.support_services.compile_prompt(
                skill,
                dialect,
                protocol_governed_enabled=bool(provisional_context.get("protocol_governed_enabled", False)),
                patch=(prompt_patch or None),
            )
        if memory_context and not self.should_suppress_reference_context_for_cards_runtime(cards_runtime):
            system_prompt += f"\n\nPROJECT CONTEXT (PAST DECISIONS):\n{memory_context}"

        prompt_metadata["prompt_checksum"] = hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()[:16]
        if prompt_patch:
            prompt_patch_checksum = hashlib.sha256(prompt_patch.encode("utf-8")).hexdigest()[:16]
            prompt_metadata["prompt_patch_applied"] = True
            prompt_metadata["prompt_patch_label"] = prompt_patch_label or "runtime_patch"
            prompt_metadata["prompt_patch_checksum"] = prompt_patch_checksum
            prompt_layers["patch"] = {
                "applied": True,
                "label": prompt_patch_label or "runtime_patch",
                "checksum": prompt_patch_checksum,
            }

        context = self.build_turn_context(
            run_id=run_id,
            issue=issue,
            seat_name=seat_name,
            roles_to_load=roles_to_load,
            turn_status=turn_status,
            selected_model=selected_model,
            dependency_context=dependency_context,
            runtime_verifier_ok=(None if runtime_result is None else bool(runtime_result.ok)),
            prompt_metadata=prompt_metadata,
            prompt_layers=prompt_layers,
            idesign_enabled=idesign_enabled,
            resume_mode=resume_mode,
            skill_tool_bindings=skill_tool_bindings,
            cards_runtime=cards_runtime,
        )
        return context, system_prompt
