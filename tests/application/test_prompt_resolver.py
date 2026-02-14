from __future__ import annotations

import pytest

from orket.application.services.prompt_resolver import PromptResolver
from orket.schema import DialectConfig, SkillConfig


def _skill() -> SkillConfig:
    return SkillConfig(
        name="architect",
        intent="Design architecture",
        responsibilities=["Produce design decisions"],
        tools=["write_file", "update_issue_status"],
        prompt_metadata={"id": "role.architect", "version": "1.2.0", "status": "stable"},
    )


def _dialect() -> DialectConfig:
    return DialectConfig(
        model_family="qwen",
        dsl_format="JSON",
        constraints=["Return JSON only"],
        hallucination_guard="No extra prose",
        system_prefix="DIALECT PREFIX",
        prompt_metadata={"id": "dialect.qwen", "version": "3.0.1", "status": "stable"},
    )


def test_prompt_resolver_composes_deterministically() -> None:
    skill = _skill()
    dialect = _dialect()
    context = {
        "prompt_context_profile": "long_project",
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["code_review"],
    }
    resolution_a = PromptResolver.resolve(
        skill=skill,
        dialect=dialect,
        context=context,
        guards=["hallucination", "security"],
    )
    resolution_b = PromptResolver.resolve(
        skill=skill,
        dialect=dialect,
        context=context,
        guards=["hallucination", "security"],
    )

    assert resolution_a.system_prompt == resolution_b.system_prompt
    assert resolution_a.metadata["prompt_checksum"] == resolution_b.metadata["prompt_checksum"]
    assert resolution_a.metadata["prompt_id"] == "role.architect+dialect.qwen"
    assert resolution_a.metadata["prompt_version"] == "1.2.0/3.0.1"
    assert resolution_a.metadata["selection_policy"] == "stable"
    assert resolution_a.layers["guards"] == ["hallucination", "security"]
    assert resolution_a.layers["context_profile"] == "long_project"


def test_prompt_resolver_applies_prefix_guards_and_context_overlay() -> None:
    resolution = PromptResolver.resolve(
        skill=_skill(),
        dialect=_dialect(),
        context={
            "prompt_context_profile": "default",
            "required_read_paths": ["agent_output/main.py"],
        },
        guards=["security"],
    )

    assert resolution.system_prompt.startswith("DIALECT PREFIX")
    assert "PROMPT GUARD OVERLAYS" in resolution.system_prompt
    assert "security" in resolution.system_prompt
    assert "PROMPT CONTEXT OVERLAYS" in resolution.system_prompt
    assert "required_read_paths" in resolution.system_prompt


def test_prompt_resolver_stable_policy_strict_rejects_non_stable_assets() -> None:
    skill = _skill().model_copy(update={"prompt_metadata": {"id": "role.architect", "version": "1.2.0", "status": "draft"}})
    dialect = _dialect()

    with pytest.raises(ValueError, match="Stable policy requires stable assets"):
        PromptResolver.resolve(
            skill=skill,
            dialect=dialect,
            context={"prompt_selection_policy": "stable", "prompt_selection_strict": True},
        )


def test_prompt_resolver_exact_policy_strict_requires_matching_version() -> None:
    skill = _skill()
    dialect = _dialect()

    with pytest.raises(ValueError, match="Exact policy version mismatch"):
        PromptResolver.resolve(
            skill=skill,
            dialect=dialect,
            context={
                "prompt_selection_policy": "exact",
                "prompt_selection_strict": True,
                "prompt_version_exact": "9.9.9/9.9.9",
            },
        )


def test_prompt_resolver_exact_policy_allows_metadata_only_rollback() -> None:
    dialect = _dialect()
    current = _skill().model_copy(
        update={"prompt_metadata": {"id": "role.architect", "version": "2.0.0", "status": "stable"}}
    )
    rollback = _skill().model_copy(
        update={"prompt_metadata": {"id": "role.architect", "version": "1.9.0", "status": "stable"}}
    )

    current_resolution = PromptResolver.resolve(
        skill=current,
        dialect=dialect,
        context={
            "prompt_selection_policy": "exact",
            "prompt_selection_strict": True,
            "prompt_version_exact": "2.0.0/3.0.1",
        },
    )
    rollback_resolution = PromptResolver.resolve(
        skill=rollback,
        dialect=dialect,
        context={
            "prompt_selection_policy": "exact",
            "prompt_selection_strict": True,
            "prompt_version_exact": "1.9.0/3.0.1",
        },
    )

    assert current_resolution.metadata["prompt_version"] == "2.0.0/3.0.1"
    assert rollback_resolution.metadata["prompt_version"] == "1.9.0/3.0.1"


def test_prompt_resolver_normalizes_and_deduplicates_guard_layers() -> None:
    resolution = PromptResolver.resolve(
        skill=_skill(),
        dialect=_dialect(),
        guards=["Hallucination", "security", "hallucination", "consistency"],
    )
    assert resolution.layers["guards"] == ["hallucination", "security", "consistency"]
    assert resolution.metadata["guard_count"] == 3


def test_prompt_resolver_rejects_unknown_guard_layers() -> None:
    with pytest.raises(ValueError, match="Unsupported guard layer"):
        PromptResolver.resolve(
            skill=_skill(),
            dialect=_dialect(),
            guards=["governance"],
        )


def test_prompt_resolver_rejects_rule_ownership_overlap() -> None:
    with pytest.raises(ValueError, match="Rule ownership conflict"):
        PromptResolver.resolve(
            skill=_skill(),
            dialect=_dialect(),
            context={
                "prompt_rule_ids": ["STYLE.001", "FORMAT.001"],
                "runtime_guard_rule_ids": ["HALLUCINATION.001", "FORMAT.001"],
            },
        )


def test_prompt_resolver_allows_disjoint_rule_ownership() -> None:
    resolution = PromptResolver.resolve(
        skill=_skill(),
        dialect=_dialect(),
        context={
            "prompt_rule_ids": ["STYLE.001", "FORMAT.001"],
            "runtime_guard_rule_ids": ["HALLUCINATION.001", "SECURITY.001"],
        },
    )
    assert resolution.metadata["prompt_id"] == "role.architect+dialect.qwen"
