from pathlib import Path
from orket import load_flow
import json


def test_default_flow_loads():
    flow_path = Path("model/flow/standard.json")
    assert flow_path.exists(), "Default Flow file missing"

    flow = load_flow(flow_path)

    # Validate venue
    venue_path = Path(flow.raw["venue"])
    assert venue_path.exists(), f"Venue file missing: {venue_path}"

    # Validate band
    band_path = Path(flow.raw["band"])
    assert band_path.exists(), f"Band file missing: {band_path}"

    # Validate score
    score_path = Path(flow.raw["score"])
    assert score_path.exists(), f"Score file missing: {score_path}"


def test_default_task_exists():
    task_path = Path("examples/hello/task.json")
    assert task_path.exists(), "Default task file missing"

    data = json.loads(task_path.read_text(encoding="utf-8"))
    assert "description" in data, "Task missing required 'description' field"