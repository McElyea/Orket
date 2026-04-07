from __future__ import annotations

import ast
import hashlib
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from orket.kernel.v1.canonical import first_diff_path, odr_canonical_json_bytes, odr_raw_signature
from orket.kernel.v1.odr.core import ReactorConfig, ReactorState, run_round

pytestmark = pytest.mark.contract

SEED = 1729
EXPECTED_TORTURE_SHA256 = "f9e7532a418b78dd71365731fdb0375cd93871c7716d85efb51f7d22fe97ea36"
EXPECTED_NEAR_MISS_SHA256 = "10913f9ce3bcdb66d57259ef520dab6873b33edd2dd03ea1a1739e5bb85752fd"
EXPECTED_HEADER_ORDER_SHA256 = "bda65e1c777deba0d6aa5efbe02eb107c3d6a1d88f84960fe8ee58108a7af72f"


def _fixture_path(name: str) -> Path:
    return Path(__file__).parent / "vectors" / "odr" / name


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads(_fixture_path(name).read_text(encoding="utf-8"))


def _permute_fixture(fixture: dict[str, Any], seed: int, perm_index: int) -> dict[str, Any]:
    payload = json.loads(json.dumps(fixture))
    rng = random.Random(seed + (perm_index * 7919))
    graph = payload.get("graph", {})
    for key in ("nodes", "edges", "relationships", "links", "refs"):
        values = graph.get(key)
        if isinstance(values, list):
            rng.shuffle(values)
    return payload


def _run_fixture_payload(payload: dict[str, Any], *, rounds: int = 0) -> dict[str, Any]:
    cfg = ReactorConfig()
    state = ReactorState()

    all_rounds = payload.get("rounds", [])
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
        "fixture_id": payload.get("id"),
        "graph": payload.get("graph", {}),
        "history_v": list(state.history_v),
        "history_rounds": list(state.history_rounds),
        "stop_reason": state.stop_reason,
    }


def _run_fixture(name: str, *, seed: int, perm_index: int, rounds: int = 0) -> dict[str, Any]:
    fixture = _permute_fixture(_load_fixture(name), seed, perm_index)
    return _run_fixture_payload(fixture, rounds=rounds)


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


def _header_order_violation_output() -> dict[str, Any]:
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


def _code_leak_output() -> dict[str, Any]:
    cfg = ReactorConfig()
    state = ReactorState()
    architect = (
        "### REQUIREMENT\nKeep runtime outputs free of code blocks.\n\n"
        "### CHANGELOG\n- baseline\n\n"
        "### ASSUMPTIONS\n- deterministic\n\n"
        "### OPEN_QUESTIONS\n- none\n"
    )
    auditor = (
        "### CRITIQUE\n```python\nprint('x')\n```\n\n"
        "### PATCHES\n- p\n\n"
        "### EDGE_CASES\n- e\n\n"
        "### TEST_GAPS\n- t\n"
    )
    state = run_round(state, architect, auditor, cfg)
    return {
        "stop_reason": state.stop_reason,
        "trace": state.history_rounds[-1],
    }


def _semantic_node_key(node: dict[str, Any]) -> str:
    if node.get("dto_type") is not None and node.get("id") is not None:
        return f"{node.get('dto_type')}::{node.get('id')}"
    if node.get("raw_id") is not None:
        return f"raw::{node.get('raw_id')}"
    return json.dumps(node, sort_keys=True, separators=(",", ":"))


def _dedupe_metrics(graph: dict[str, Any]) -> dict[str, Any]:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    pre = len(nodes)
    post = len({_semantic_node_key(node) for node in nodes if isinstance(node, dict)})
    reduction_pct = ((pre - post) / max(1, pre)) if pre else 0.0
    return {
        "nodes_pre": pre,
        "nodes_post": post,
        "edges_post": len(edges),
        "reduction_pct": reduction_pct,
    }


def _print_metrics_line(fixture_id: str, metrics: dict[str, Any]) -> None:
    print(
        f"fixture={fixture_id} nodes_pre={metrics['nodes_pre']} nodes_post={metrics['nodes_post']} "
        f"edges_post={metrics['edges_post']} reduction_pct={metrics['reduction_pct']:.6f}"
    )


def _parse_repro_output(text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def _generated_fixture_deep_chain(size: int) -> dict[str, Any]:
    architect_raw = (
        "### REQUIREMENT\nscale deep fixture\n\n"
        "### CHANGELOG\n- baseline\n\n"
        "### ASSUMPTIONS\n- deterministic\n\n"
        "### OPEN_QUESTIONS\n- none\n"
    )
    auditor_raw = (
        "### CRITIQUE\n- c\n\n"
        "### PATCHES\n- p\n\n"
        "### EDGE_CASES\n- e\n\n"
        "### TEST_GAPS\n- t\n"
    )
    nodes = [{"raw_id": f"N{i}", "dto_type": "req", "id": f"N{i}", "name": f"Node {i}"} for i in range(size)]
    edges = [
        {"from": f"N{i}", "label": "depends_on", "to": f"N{i+1}"}
        for i in range(max(0, size - 1))
    ]
    return {
        "id": f"generated_deep_chain_{size}",
        "graph": {"nodes": nodes, "edges": edges},
        "rounds": [
            {
                "architect_raw": architect_raw,
                "auditor_raw": auditor_raw,
            }
        ],
    }


def _generated_fixture_wide_fan(size: int) -> dict[str, Any]:
    architect_raw = (
        "### REQUIREMENT\nscale wide fixture\n\n"
        "### CHANGELOG\n- baseline\n\n"
        "### ASSUMPTIONS\n- deterministic\n\n"
        "### OPEN_QUESTIONS\n- none\n"
    )
    auditor_raw = (
        "### CRITIQUE\n- c\n\n"
        "### PATCHES\n- p\n\n"
        "### EDGE_CASES\n- e\n\n"
        "### TEST_GAPS\n- t\n"
    )
    nodes = [{"raw_id": "HUB", "dto_type": "req", "id": "HUB", "name": "Hub"}]
    nodes.extend(
        {"raw_id": f"L{i}", "dto_type": "req", "id": f"L{i}", "name": f"Leaf {i}"}
        for i in range(size)
    )
    edges = [{"from": f"L{i}", "label": "points_to", "to": "HUB"} for i in range(size)]
    return {
        "id": f"generated_wide_fan_{size}",
        "graph": {"nodes": nodes, "edges": edges},
        "rounds": [
            {
                "architect_raw": architect_raw,
                "auditor_raw": auditor_raw,
            }
        ],
    }


def _run_scale_checks() -> None:
    deep_size = int(os.getenv("ODR_SCALE_DEEP", "2000"))
    wide_size = int(os.getenv("ODR_SCALE_WIDE", "5000"))
    scale_permutations = int(os.getenv("ODR_SCALE_PERMUTATIONS", "5"))
    timeout_seconds = float(os.getenv("ODR_SCALE_TIMEOUT_SECONDS", "60"))

    for fixture in (_generated_fixture_deep_chain(deep_size), _generated_fixture_wide_fan(wide_size)):
        start = time.monotonic()
        base_payload = _permute_fixture(fixture, SEED, 0)
        base_output = _run_fixture_payload(base_payload)
        base_bytes = odr_canonical_json_bytes(base_output)

        for perm_index in range(scale_permutations):
            output = _run_fixture_payload(_permute_fixture(fixture, SEED, perm_index))
            _assert_bytes_equal(
                expected=base_bytes,
                actual=odr_canonical_json_bytes(output),
                seed=SEED,
                perm_index=perm_index,
                round_index=1,
                stop_reason=str(output.get("stop_reason") or "NONE"),
                reason="PERMUTATION_DEPENDENT",
            )

        reparsed = json.loads(base_bytes.decode("utf-8"))
        _assert_bytes_equal(
            expected=base_bytes,
            actual=odr_canonical_json_bytes(reparsed),
            seed=SEED,
            perm_index=0,
            round_index=1,
            stop_reason=str(base_output.get("stop_reason") or "NONE"),
            reason="NOT_IDEMPOTENT",
        )

        elapsed = time.monotonic() - start
        if elapsed > timeout_seconds:
            pytest.fail(
                _fail_line(
                    seed=SEED,
                    perm_index=0,
                    round_index=1,
                    path="$",
                    stop_reason=str(base_output.get("stop_reason") or "NONE"),
                    reason="CANON_MISMATCH",
                )
            )


def _run_gate(permutations: int, repeats: int, *, include_scale: bool = False) -> None:
    base_output = _run_fixture("odr_torture_pack.json", seed=SEED, perm_index=0)
    base_raw_signature = odr_raw_signature(base_output)
    base_bytes = odr_canonical_json_bytes(base_output)
    base_hash = _sha256(base_bytes)
    if base_hash != EXPECTED_TORTURE_SHA256:
        pytest.fail(
            _fail_line(
                seed=SEED,
                perm_index=0,
                round_index=1,
                path="$",
                stop_reason=str(base_output.get("stop_reason") or "NONE"),
                reason="CANON_MISMATCH",
            )
        )

    for perm_index in range(permutations):
        output = _run_fixture("odr_torture_pack.json", seed=SEED, perm_index=perm_index)
        _assert_bytes_equal(
            expected=base_bytes,
            actual=odr_canonical_json_bytes(output),
            seed=SEED,
            perm_index=perm_index,
            round_index=max(1, len(output.get("history_rounds", []))),
            stop_reason=str(output.get("stop_reason") or "NONE"),
            reason="PERMUTATION_DEPENDENT",
        )

    reparsed = json.loads(base_bytes.decode("utf-8"))
    fixed_point = odr_canonical_json_bytes(reparsed)
    _assert_bytes_equal(
        expected=base_bytes,
        actual=fixed_point,
        seed=SEED,
        perm_index=0,
        round_index=1,
        stop_reason=str(base_output.get("stop_reason") or "NONE"),
        reason="NOT_IDEMPOTENT",
    )

    torture_metrics = _dedupe_metrics(base_output["graph"])
    _print_metrics_line("odr_torture_pack", torture_metrics)
    if torture_metrics["reduction_pct"] <= 0.0:
        pytest.fail(
            _fail_line(
                seed=SEED,
                perm_index=0,
                round_index=1,
                path="$/graph/nodes",
                stop_reason=str(base_output.get("stop_reason") or "NONE"),
                reason="CANON_MISMATCH",
            )
        )

    near_output = _run_fixture("odr_near_miss.json", seed=SEED, perm_index=0)
    near_bytes = odr_canonical_json_bytes(near_output)
    near_hash = _sha256(near_bytes)
    if near_hash != EXPECTED_NEAR_MISS_SHA256:
        pytest.fail(
            _fail_line(
                seed=SEED,
                perm_index=0,
                round_index=1,
                path="$",
                stop_reason=str(near_output.get("stop_reason") or "NONE"),
                reason="CANON_MISMATCH",
            )
        )

    near_metrics = _dedupe_metrics(near_output["graph"])
    _print_metrics_line("odr_near_miss", near_metrics)
    if near_metrics["reduction_pct"] != 0.0:
        pytest.fail(
            _fail_line(
                seed=SEED,
                perm_index=0,
                round_index=1,
                path="$/graph/nodes",
                stop_reason=str(near_output.get("stop_reason") or "NONE"),
                reason="NEAR_MISS_DEDUPED",
            )
        )

    header_order_one = _header_order_violation_output()
    header_order_two = _header_order_violation_output()
    header_order_one_bytes = odr_canonical_json_bytes(header_order_one)
    header_order_two_bytes = odr_canonical_json_bytes(header_order_two)
    _assert_bytes_equal(
        expected=header_order_one_bytes,
        actual=header_order_two_bytes,
        seed=SEED,
        perm_index=0,
        round_index=1,
        stop_reason=str(header_order_one.get("stop_reason") or "NONE"),
        reason="HEADER_ORDER_VIOLATION_NONDETERMINISTIC",
    )
    if _sha256(header_order_one_bytes) != EXPECTED_HEADER_ORDER_SHA256:
        pytest.fail(
            _fail_line(
                seed=SEED,
                perm_index=0,
                round_index=1,
                path="$",
                stop_reason=str(header_order_one.get("stop_reason") or "NONE"),
                reason="HEADER_ORDER_VIOLATION_NONDETERMINISTIC",
            )
        )

    script = Path("tools/repro_odr_gate.py")
    fixture = _fixture_path("odr_torture_pack.json")
    seen_hashes = set()
    seen_raw_signatures = set()
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
            "--print-raw-signature",
        ]
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if proc.returncode != 0:
            pytest.fail(proc.stdout.strip() or proc.stderr.strip() or "repro_odr_gate failed")

        parsed = _parse_repro_output(proc.stdout)
        hash_value = parsed.get("canon_hash", "")
        raw_value = parsed.get("raw_signature", "")
        if not hash_value or not raw_value:
            pytest.fail(
                _fail_line(
                    seed=SEED,
                    perm_index=0,
                    round_index=repeat_idx + 1,
                    path="$",
                    stop_reason=str(base_output.get("stop_reason") or "NONE"),
                    reason="REPEAT_RUN_NONDETERMINISM",
                )
            )
        seen_hashes.add(hash_value)
        seen_raw_signatures.add(raw_value)
        if hash_value != EXPECTED_TORTURE_SHA256:
            pytest.fail(
                _fail_line(
                    seed=SEED,
                    perm_index=0,
                    round_index=repeat_idx + 1,
                    path="$",
                    stop_reason=str(base_output.get("stop_reason") or "NONE"),
                    reason="REPEAT_RUN_NONDETERMINISM",
                )
            )
        if raw_value != base_raw_signature:
            pytest.fail(
                _fail_line(
                    seed=SEED,
                    perm_index=0,
                    round_index=repeat_idx + 1,
                    path="$",
                    stop_reason=str(base_output.get("stop_reason") or "NONE"),
                    reason="RAW_SIGNATURE_MISMATCH",
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
                reason="REPEAT_RUN_NONDETERMINISM",
            )
        )

    if len(seen_raw_signatures) != 1:
        pytest.fail(
            _fail_line(
                seed=SEED,
                perm_index=0,
                round_index=1,
                path="$",
                stop_reason=str(base_output.get("stop_reason") or "NONE"),
                reason="RAW_SIGNATURE_MISMATCH",
            )
        )

    if include_scale:
        _run_scale_checks()


def test_odr_determinism_gate_pr() -> None:
    permutations = int(os.getenv("ODR_PERMUTATIONS", "10"))
    repeats = int(os.getenv("ODR_REPEATS", "5"))
    include_scale = os.getenv("ODR_INCLUDE_SCALE", "0") == "1"
    _run_gate(permutations=permutations, repeats=repeats, include_scale=include_scale)


def test_odr_determinism_gate_imports_odr_canonicalizer_only() -> None:
    module = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert "orket.kernel.v1.canonical" in imported_modules
    assert "orket.kernel.v1.canon" not in imported_modules


def test_code_leak_shape_detection_fires() -> None:
    leaked = _code_leak_output()

    assert leaked["stop_reason"] == "CODE_LEAK"
    assert leaked["trace"]["metrics"]["code_leak_hit"] is True
    assert leaked["trace"]["code_leak_matches_hard"]
