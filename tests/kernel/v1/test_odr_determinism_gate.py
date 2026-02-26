from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

from orket.kernel.v1.canon import canonical_bytes, first_diff_path
from orket.kernel.v1.odr.core import ReactorConfig, ReactorState, run_round

SEED = 1729
EXPECTED_TORTURE_SHA256 = "d2731af1edec31bfc2efa6f27378fc7f38f6e72694e62c4702ccd31155e6b44a"
EXPECTED_NEAR_MISS_SHA256 = "1d5d50f95373b099a5b33a85cbf9ba2043a95ebe3cc02f76c7c96b7a8f8fdf49"
EXPECTED_SHAPE_SHA256 = "ef5b19474c6f3bb4a819012c98e537582ccf5b39bbd1c2a24938c3cfb29c4324"


def _fixture_path(name: str) -> Path:
    return Path(__file__).parent / "vectors" / "odr" / name


def _load_fixture(name: str) -> Dict[str, Any]:
    return json.loads(_fixture_path(name).read_text(encoding="utf-8"))


def _permute_fixture(fixture: Dict[str, Any], seed: int, perm_index: int) -> Dict[str, Any]:
    import random

    payload = json.loads(json.dumps(fixture))
    rng = random.Random(seed + (perm_index * 7919))
    graph = payload.get("graph", {})
    for key in ("nodes", "edges", "relationships", "links", "refs"):
        values = graph.get(key)
        if isinstance(values, list):
            rng.shuffle(values)
    return payload


def _run_fixture(name: str, *, seed: int, perm_index: int, rounds: int = 0) -> Dict[str, Any]:
    fixture = _permute_fixture(_load_fixture(name), seed, perm_index)
    cfg = ReactorConfig()
    state = ReactorState()

    all_rounds = fixture.get("rounds", [])
    for idx, round_payload in enumerate(all_rounds):
        if rounds > 0 and idx >= rounds:
            break
        state = run_round(
            state,
            str(round_payload.get("architect_raw", "")),
            str(round_payload.get("auditor_raw", "")),
            cfg,
        )
        if state.stop_reason is not None:
            break

    return {
        "fixture_id": fixture.get("id"),
        "graph": fixture.get("graph", {}),
        "history_v": list(state.history_v),
        "history_rounds": list(state.history_rounds),
        "stop_reason": state.stop_reason,
    }


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fail_line(*, seed: int, perm_index: int, round_index: int, path: str, stop_reason: str, reason: str) -> str:
    return (
        f"seed={seed} perm_index={perm_index} round={round_index} "
        f"first_diff_path={path} stop_reason={stop_reason} failure_reason={reason}"
    )


def _assert_bytes_equal(
    *,
    expected: bytes,
    actual: bytes,
    seed: int,
    perm_index: int,
    round_index: int,
    stop_reason: str,
    reason: str,
) -> None:
    if actual == expected:
        return
    path = first_diff_path(expected, actual)
    pytest.fail(
        _fail_line(
            seed=seed,
            perm_index=perm_index,
            round_index=round_index,
            path=path,
            stop_reason=stop_reason,
            reason=reason,
        )
    )


def _shape_violation_output() -> Dict[str, Any]:
    cfg = ReactorConfig()
    state = ReactorState()
    architect = (
        "### REQUIREMENT\nX\n\n"
        "### ASSUMPTIONS\n- a\n\n"
        "### CHANGELOG\n- c\n\n"
        "### OPEN_QUESTIONS\n- q\n"
    )
    auditor = (
        "### CRITIQUE\n- c\n\n"
        "### PATCHES\n- p\n\n"
        "### EDGE_CASES\n- e\n\n"
        "### TEST_GAPS\n- t\n"
    )
    state = run_round(state, architect, auditor, cfg)
    return {
        "stop_reason": state.stop_reason,
        "trace": state.history_rounds[-1],
    }


def _run_gate(permutations: int, repeats: int) -> None:
    base_output = _run_fixture("odr_torture_pack.json", seed=SEED, perm_index=0)
    base_bytes = canonical_bytes(base_output)
    base_hash = _sha256(base_bytes)
    if base_hash != EXPECTED_TORTURE_SHA256:
        pytest.fail(
            _fail_line(
                seed=SEED,
                perm_index=0,
                round_index=1,
                path="$",
                stop_reason=str(base_output.get("stop_reason") or "NONE"),
                reason="GOLDEN_HASH_MISMATCH",
            )
        )

    for perm_index in range(permutations):
        output = _run_fixture("odr_torture_pack.json", seed=SEED, perm_index=perm_index)
        actual = canonical_bytes(output)
        _assert_bytes_equal(
            expected=base_bytes,
            actual=actual,
            seed=SEED,
            perm_index=perm_index,
            round_index=max(1, len(output.get("history_rounds", []))),
            stop_reason=str(output.get("stop_reason") or "NONE"),
            reason="CANON_MISMATCH",
        )

    reparsed = json.loads(base_bytes.decode("utf-8"))
    fixed_point = canonical_bytes(reparsed)
    _assert_bytes_equal(
        expected=base_bytes,
        actual=fixed_point,
        seed=SEED,
        perm_index=0,
        round_index=1,
        stop_reason=str(base_output.get("stop_reason") or "NONE"),
        reason="NOT_IDEMPOTENT",
    )

    near_output = _run_fixture("odr_near_miss.json", seed=SEED, perm_index=0)
    near_bytes = canonical_bytes(near_output)
    near_hash = _sha256(near_bytes)
    if near_hash != EXPECTED_NEAR_MISS_SHA256:
        pytest.fail(
            _fail_line(
                seed=SEED,
                perm_index=0,
                round_index=1,
                path="$",
                stop_reason=str(near_output.get("stop_reason") or "NONE"),
                reason="NEAR_MISS_GOLDEN_HASH_MISMATCH",
            )
        )

    nodes = near_output["graph"].get("nodes", [])
    identities = {(str(node.get("raw_id")), str(node.get("dto_type")), str(node.get("id"))) for node in nodes}
    if len(identities) != 2:
        pytest.fail(
            _fail_line(
                seed=SEED,
                perm_index=0,
                round_index=1,
                path="$/graph/nodes",
                stop_reason=str(near_output.get("stop_reason") or "NONE"),
                reason="NEAR_MISS_COLLAPSED",
            )
        )

    shape_one = _shape_violation_output()
    shape_two = _shape_violation_output()
    shape_one_bytes = canonical_bytes(shape_one)
    shape_two_bytes = canonical_bytes(shape_two)
    _assert_bytes_equal(
        expected=shape_one_bytes,
        actual=shape_two_bytes,
        seed=SEED,
        perm_index=0,
        round_index=1,
        stop_reason=str(shape_one.get("stop_reason") or "NONE"),
        reason="NONDETERMINISTIC_ERROR",
    )
    if _sha256(shape_one_bytes) != EXPECTED_SHAPE_SHA256:
        pytest.fail(
            _fail_line(
                seed=SEED,
                perm_index=0,
                round_index=1,
                path="$",
                stop_reason=str(shape_one.get("stop_reason") or "NONE"),
                reason="SHAPE_GOLDEN_HASH_MISMATCH",
            )
        )

    script = Path("tools/repro_odr_gate.py")
    fixture = _fixture_path("odr_torture_pack.json")
    seen_hashes = set()
    for repeat_idx in range(repeats):
        cmd = [
            sys.executable,
            str(script),
            "--seed",
            str(SEED),
            "--fixture",
            str(fixture),
            "--perm-index",
            "0",
            "--rounds",
            "0",
            "--mode",
            "pr",
            "--print-canon-hash",
        ]
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if proc.returncode != 0:
            pytest.fail(proc.stdout.strip() or proc.stderr.strip() or "repro_odr_gate failed")
        value = proc.stdout.strip().splitlines()[-1].strip()
        seen_hashes.add(value)
        if value != EXPECTED_TORTURE_SHA256:
            pytest.fail(
                _fail_line(
                    seed=SEED,
                    perm_index=0,
                    round_index=repeat_idx + 1,
                    path="$",
                    stop_reason=str(base_output.get("stop_reason") or "NONE"),
                    reason="REPEAT_RUN_HASH_MISMATCH",
                )
            )

    if len(seen_hashes) != 1:
        pytest.fail(
            _fail_line(
                seed=SEED,
                perm_index=0,
                round_index=1,
                path="$",
                stop_reason=str(base_output.get("stop_reason") or "NONE"),
                reason="REPEAT_RUN_NONDETERMINISTIC",
            )
        )


def test_odr_determinism_gate_pr() -> None:
    permutations = int(os.getenv("ODR_PERMUTATIONS", "10"))
    repeats = int(os.getenv("ODR_REPEATS", "5"))
    _run_gate(permutations=permutations, repeats=repeats)


def test_odr_determinism_gate_nightly() -> None:
    if os.getenv("ODR_GATE_NIGHTLY", "0") != "1":
        pytest.skip("nightly ODR gate disabled")
    permutations = int(os.getenv("ODR_PERMUTATIONS", "50"))
    repeats = int(os.getenv("ODR_REPEATS", "20"))
    _run_gate(permutations=permutations, repeats=repeats)
