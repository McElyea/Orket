from __future__ import annotations

import time

import pytest

import orket.application.review.run_service as run_service_module

pytestmark = pytest.mark.unit


def _decode_timestamp_ms(run_id: str) -> int:
    value = 0
    for char in run_id[:10]:
        value = (value << 5) | run_service_module._ULID_ALPHABET.index(char)
    return value


def test_review_run_ulids_are_monotonic_valid_and_timestamped(monkeypatch) -> None:
    """Layer: unit. Verifies review-run IDs use monotonic ULID-compatible timestamp encoding."""
    monkeypatch.setattr(run_service_module, "_last_ulid_timestamp_ms", -1)
    monkeypatch.setattr(run_service_module, "_last_ulid_randomness", -1)
    before_ms = time.time_ns() // 1_000_000

    run_ids = [run_service_module._generate_ulid() for _ in range(1000)]

    after_ms = time.time_ns() // 1_000_000
    assert run_ids == sorted(run_ids)
    assert len(set(run_ids)) == 1000
    assert all(len(run_id) == 26 for run_id in run_ids)
    assert all(set(run_id).issubset(set(run_service_module._ULID_ALPHABET)) for run_id in run_ids)
    timestamp_ms = _decode_timestamp_ms(run_ids[0])
    assert before_ms - 1000 <= timestamp_ms <= after_ms + 1000


def test_ulid_component_encoding_matches_spec_boundaries() -> None:
    """Layer: unit. Verifies ULID timestamp and randomness components use fixed-width Crockford encoding."""
    assert run_service_module._encode_crockford_base32(0, length=10) == "0000000000"
    assert run_service_module._encode_crockford_base32((1 << 48) - 1, length=10) == "7ZZZZZZZZZ"
    assert run_service_module._encode_crockford_base32(0, length=16) == "0000000000000000"
    assert run_service_module._encode_crockford_base32((1 << 80) - 1, length=16) == "ZZZZZZZZZZZZZZZZ"
