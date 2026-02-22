from __future__ import annotations

from pathlib import Path


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_memory_determinism_trace_schema_contract() -> None:
    path = Path("docs/projects/archive/MemoryPersistence/MEMORY_DETERMINISM_TRACE_SCHEMA.md")
    assert path.exists(), f"Missing schema doc: {path}"
    text = _read(path)

    required_tokens = [
        "memory.determinism_trace.v1",
        "run_id",
        "workflow_id",
        "memory_snapshot_id",
        "visibility_mode",
        "model_config_id",
        "policy_set_id",
        "determinism_trace_schema_version",
        "event_id",
        "index",
        "tool_calls",
        "guardrails_triggered",
        "retrieval_event_ids",
        "output_type",
        "output_shape_hash",
        "tool_result_fingerprint",
        "side_effect_fingerprint",
        "excluded from equivalence matching",
        "retained for at least 14 days",
        "10 MB per run artifact",
        "truncation marker field",
    ]

    missing = [token for token in required_tokens if token not in text]
    assert not missing, f"Missing required determinism trace contract tokens: {missing}"


def test_memory_determinism_trace_schema_has_required_output_shape_examples() -> None:
    path = Path("docs/projects/archive/MemoryPersistence/MEMORY_DETERMINISM_TRACE_SCHEMA.md")
    text = _read(path)

    required_examples = [
        '{ "type": "text", "sections": ["intro", "body", "conclusion"] }',
        '{ "type": "plan", "steps": [ { "id": 1, "action": "analyze" }, { "id": 2, "action": "generate" } ] }',
        '{ "type": "code_patch", "files": [ { "path": "foo.py", "changes": [...] } ] }',
    ]

    missing = [example for example in required_examples if example not in text]
    assert not missing, "Determinism trace schema must include text/plan/code_patch canonical examples."


def test_memory_canonicalization_schema_has_edge_behavior_contract() -> None:
    path = Path("docs/projects/archive/MemoryPersistence/MEMORY_CANONICALIZATION_JSON_V1.md")
    text = _read(path)
    required_tokens = [
        "Unicode normalization form: `NFC`",
        "ISO 8601 UTC with trailing `Z`",
        "missing means field omitted",
        "null` means field explicitly present with null value",
    ]
    missing = [token for token in required_tokens if token not in text]
    assert not missing, f"Missing canonicalization edge-behavior tokens: {missing}"
