"""Integration: independent reference algorithms exercise the retained native oracle."""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from orket.adapters.storage.card_acceptance_evidence_store import CardAcceptanceEvidenceStore
from orket.application.services.card_acceptance_service import CardAcceptanceService
from orket.application.services.runtime_verifier import RuntimeVerifier
from orket.core.contracts.card_acceptance_inputs import PythonCliAcceptance
from scripts.benchmarks.task_acceptance import declare_task_acceptance

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
TASKS = json.loads((ROOT / "benchmarks/task_bank/v2_realworld/tasks.json").read_text(encoding="utf-8"))
REFERENCES = {
    "032": '''def min_meeting_rooms(intervals):
    events = [(s, 1) for s, e in intervals] + [(e, -1) for s, e in intervals]
    active = peak = 0
    for _, delta in sorted(events):
        active += delta
        peak = max(peak, active)
    return peak
''',
    "040": '''def is_valid_sudoku(board):
    groups = list(board) + [list(column) for column in zip(*board)]
    groups += [[board[r+i][c+j] for i in range(3) for j in range(3)]
               for r in range(0, 9, 3) for c in range(0, 9, 3)]
    for group in groups:
        digits = [value for value in group if value != '.']
        if len(digits) != len(set(digits)):
            return False
    return True
''',
    "043": '''def largest_histogram_area(heights):
    areas = [min(heights[a:b]) * (b-a)
             for a in range(len(heights)) for b in range(a+1, len(heights)+1)]
    return max(areas, default=0)
''',
    "055": '''def dag_shortest_path(n, edges, start, end):
    costs = [float('inf')] * n
    costs[start] = 0
    for _ in range(n-1):
        previous = costs[:]
        for u, v, weight in edges:
            costs[v] = min(costs[v], previous[u] + weight)
    return -1 if costs[end] == float('inf') else costs[end]
''',
    "060": '''def asteroid_collision(values):
    remaining = list(values)
    while True:
        pair = next((i for i in range(len(remaining)-1)
                     if remaining[i] > 0 > remaining[i+1]), None)
        if pair is None:
            return remaining
        left, right = remaining[pair:pair+2]
        survivors = [left] if left > -right else [right] if left < -right else []
        remaining[pair:pair+2] = survivors
''',
    "025": '''import argparse
import sys
from implementation import minimum_window

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('values', nargs='*')
    values = parser.parse_args().values
    if len(values) != 2:
        print('error: expected exactly 2 arguments', file=sys.stderr)
        raise SystemExit(2)
    print(minimum_window(*values))
''',
}
MINIMUM_WINDOW = '''from collections import Counter

def minimum_window(source, target):
    wanted = Counter(target)
    if not target:
        return ''
    for size in range(1, len(source)+1):
        for start in range(len(source)-size+1):
            candidate = source[start:start+size]
            counts = Counter(candidate)
            if all(counts[c] >= n for c, n in wanted.items()):
                return candidate
    return ''
'''


def prepare(root, identifier, incorrect):
    task = next(task for task in TASKS if task["id"] == identifier)
    epic = {"issues": [{"summary": "Oracle control", "note": "Declared task only"}]}
    declare_task_acceptance(epic, task, root)
    source = REFERENCES[identifier]
    if incorrect:
        function = task["evaluation"].get("function_name")
        source = f"def {function}(*args, **kwargs):\n    return None\n" if function else "print('wrong')\n"
    (root / "agent_output/main.py").write_text(source, encoding="utf-8")
    if identifier == "025":
        (root / "agent_output/implementation.py").write_text(MINIMUM_WINDOW, encoding="utf-8")
    return epic["issues"][0]["params"]


@pytest.mark.asyncio
@pytest.mark.parametrize("identifier", REFERENCES)
@pytest.mark.parametrize("incorrect", [False, True])
async def test_six_failed_task_oracles_accept_independent_answers_and_reject_wrong_ones(tmp_path, identifier, incorrect):
    params = await asyncio.to_thread(prepare, tmp_path, identifier, incorrect)
    definition = PythonCliAcceptance.model_validate(params["completion_acceptance"])
    store = CardAcceptanceEvidenceStore(tmp_path / "evidence.sqlite3")
    result = await CardAcceptanceService(store).verify(
        workspace_root=tmp_path, definition=definition, card_id=identifier,
        run_id="oracle-control", attempt_id="attempt", workload_inputs_json="{}")
    assert result.decision.sufficient is not incorrect
    retained = json.loads(await store.read(result.evidence_digest))
    assert retained["commands"]
    support = await RuntimeVerifier(tmp_path, issue_params=params).verify()
    assert support.ok is not incorrect
    assert len(params["runtime_verifier"]["json_assertions"]) == len(definition.cases)


@pytest.mark.parametrize("kind", ["card", "rock"])
def test_live_suite_rejects_metadata_bank_before_launch_or_report_replacement(tmp_path, kind):
    report = tmp_path / "report.json"
    report.write_bytes(b"previous evidence")
    result = subprocess.run(
        [sys.executable, str(ROOT / f"scripts/benchmarks/run_live_{kind}_benchmark_suite.py"),
         "--task-bank", str(ROOT / "benchmarks/task_bank/v1/tasks.json"), "--raw-out", str(report)],
        cwd=ROOT, env=dict(os.environ, ORKET_DISABLE_SANDBOX="1"),
        capture_output=True, text=True, timeout=20)
    assert result.returncode == 2 and "oracle preflight failed for task 001" in result.stderr
    assert report.read_bytes() == b"previous evidence"
