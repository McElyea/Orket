# Layer: unit
from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location("decompose_and_route_test", str(path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def test_validate_decomposition_plan_requires_full_artifact_coverage() -> None:
    module = _load_module(Path("scripts/workloads/decompose_and_route.py"))
    spec = {
        "artifacts": [
            {"path": "agent_output/schema.json"},
            {"path": "agent_output/writer.py"},
        ]
    }
    plan = {
        "summary": "test",
        "subtasks": [
            {"task_id": "A", "summary": "schema", "artifact_path": "agent_output/schema.json", "depends_on": []}
        ],
    }

    normalized, valid, errors = module._validate_decomposition_plan(plan, spec)

    assert normalized["summary"] == "test"
    assert valid is False
    assert "artifact_coverage_mismatch" in errors


def test_decomposition_contract_normalizes_scalar_dependencies() -> None:
    module = _load_module(Path("scripts/workloads/decompose_and_route.py"))
    payload = module._DecompositionContract.model_validate(
        {
            "summary": "test",
            "subtasks": [
                {"task_id": "1", "summary": "schema", "artifact_path": "agent_output/schema.json", "depends_on": None},
                {"task_id": "2", "summary": "writer", "artifact_path": "agent_output/writer.py", "depends_on": "1"},
            ],
        }
    )

    assert payload.subtasks[0].depends_on == []
    assert payload.subtasks[1].depends_on == ["1"]


def test_verify_round_trip_loads_generated_writer_and_reader(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/workloads/decompose_and_route.py"))
    workspace = tmp_path
    (workspace / "agent_output").mkdir(parents=True, exist_ok=True)
    (workspace / "agent_output" / "schema.json").write_text('{"fields":["id","title","status"]}\n', encoding="utf-8")
    (workspace / "agent_output" / "writer.py").write_text(
        "import json\n"
        "from pathlib import Path\n\n"
        "def append_task(path, task):\n"
        "    target = Path(path)\n"
        "    rows = json.loads(target.read_text(encoding='utf-8'))\n"
        "    rows.append(task)\n"
        "    target.write_text(json.dumps(rows), encoding='utf-8')\n",
        encoding="utf-8",
    )
    (workspace / "agent_output" / "reader.py").write_text(
        "import json\n"
        "from pathlib import Path\n\n"
        "def list_tasks(path):\n"
        "    return json.loads(Path(path).read_text(encoding='utf-8'))\n",
        encoding="utf-8",
    )

    report = module._verify_round_trip(
        workspace=workspace,
        spec={"sample_task": {"id": "task-1", "title": "demo", "status": "ready"}},
    )

    assert report["schema_valid"] is True
    assert report["writer_loaded"] is True
    assert report["reader_loaded"] is True
    assert report["round_trip_success"] is True
