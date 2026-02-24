from __future__ import annotations

import json
from pathlib import Path

from orket.kernel.v1.validator import compare_runs_v1


def test_replay_vectors_compare_runs_contract_surface() -> None:
    vector_path = Path("tests/kernel/v1/vectors/replay-v1.json")
    payload = json.loads(vector_path.read_text(encoding="utf-8"))
    vectors = payload["vectors"]
    assert isinstance(vectors, list) and vectors

    for vector in vectors:
        response = compare_runs_v1(
            {
                "contract_version": "kernel_api/v1",
                "run_a": vector["run_a"],
                "run_b": vector["run_b"],
                "compare_mode": "structural_parity",
            }
        )
        assert response["outcome"] == vector["expect_outcome"], vector["name"]
        if vector["expect_outcome"] == "FAIL":
            codes = [issue["code"] for issue in response["issues"]]
            assert vector["expect_code"] in codes, vector["name"]
            details = response["issues"][0]["details"]
            expected_fields = vector.get("expect_mismatch_fields")
            if expected_fields is not None:
                assert details["mismatch_fields"] == expected_fields, vector["name"]
