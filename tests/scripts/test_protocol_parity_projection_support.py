from __future__ import annotations

import pytest

from scripts.protocol.parity_projection_support import (
    extract_campaign_invalid_projection_field_counts,
    merge_invalid_projection_field_counts,
    normalize_invalid_projection_field_counts,
)


@pytest.mark.contract
def test_extract_campaign_invalid_projection_field_counts_normalizes_campaign_delta() -> None:
    payload = {
        "compatibility_telemetry_delta": {
            "sqlite_invalid_projection_field_counts": {"summary_json": 1, "artifact_json": 2},
            "protocol_invalid_projection_field_counts": {"artifact_json": 3},
        }
    }

    counts = extract_campaign_invalid_projection_field_counts(payload)

    assert counts == {
        "sqlite": {"artifact_json": 2, "summary_json": 1},
        "protocol": {"artifact_json": 3},
    }


@pytest.mark.contract
def test_normalize_invalid_projection_field_counts_defaults_to_empty_sides() -> None:
    assert normalize_invalid_projection_field_counts(None) == {"sqlite": {}, "protocol": {}}
    assert normalize_invalid_projection_field_counts({"sqlite": {"summary_json": 1}}) == {
        "sqlite": {"summary_json": 1},
        "protocol": {},
    }


@pytest.mark.contract
def test_merge_invalid_projection_field_counts_accumulates_rows() -> None:
    rows = [
        {"counts": {"sqlite": {"summary_json": 1}, "protocol": {}}},
        {"counts": {"sqlite": {"artifact_json": 2}, "protocol": {"summary_json": 3}}},
    ]

    merged = merge_invalid_projection_field_counts(rows, "counts")

    assert merged == {
        "sqlite": {"artifact_json": 2, "summary_json": 1},
        "protocol": {"summary_json": 3},
    }
