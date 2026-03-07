from __future__ import annotations

from orket.application.workflows.turn_tool_dispatcher_compatibility import resolve_compatibility_translation


# Layer: unit
def test_resolve_compatibility_translation_is_deterministic_for_identical_inputs() -> None:
    context = {
        "compatibility_mappings": {
            "openclaw.file_read": {
                "mapping_version": 1,
                "mapped_core_tools": ["workspace.read"],
                "schema_compatibility_range": ">=1.0.0 <2.0.0",
                "determinism_class": "workspace",
            }
        },
        "skill_tool_bindings": {
            "workspace.read": {
                "ring": "core",
                "determinism_class": "workspace",
            }
        },
    }
    binding = {"ring": "compatibility"}
    first, first_violation = resolve_compatibility_translation(
        tool_name="openclaw.file_read",
        tool_args={"path": "a.txt", "trace_id": "runtime-only"},
        binding=binding,
        context=context,
    )
    second, second_violation = resolve_compatibility_translation(
        tool_name="openclaw.file_read",
        tool_args={"path": "a.txt"},
        binding=binding,
        context=context,
    )

    assert first_violation is None
    assert second_violation is None
    assert first is not None
    assert second is not None
    assert first["artifact"]["translation_hash"] == second["artifact"]["translation_hash"]


# Layer: contract
def test_resolve_compatibility_translation_rejects_missing_mapping() -> None:
    translation, violation = resolve_compatibility_translation(
        tool_name="openclaw.file_read",
        tool_args={"path": "a.txt"},
        binding={"ring": "compatibility"},
        context={"compatibility_mappings": {}, "skill_tool_bindings": {}},
    )

    assert translation is None
    assert violation is not None
    assert "E_COMPAT_MAPPING_MISSING" in violation


# Layer: contract
def test_resolve_compatibility_translation_rejects_mapping_determinism_mismatch() -> None:
    translation, violation = resolve_compatibility_translation(
        tool_name="openclaw.file_read",
        tool_args={"path": "a.txt"},
        binding={"ring": "compatibility"},
        context={
            "compatibility_mappings": {
                "openclaw.file_read": {
                    "mapping_version": 1,
                    "mapped_core_tools": ["workspace.read"],
                    "schema_compatibility_range": ">=1.0.0 <2.0.0",
                    "determinism_class": "pure",
                }
            },
            "skill_tool_bindings": {
                "workspace.read": {
                    "ring": "core",
                    "determinism_class": "workspace",
                }
            },
        },
    )

    assert translation is None
    assert violation is not None
    assert "E_COMPAT_MAPPING_POLICY_VIOLATION" in violation
