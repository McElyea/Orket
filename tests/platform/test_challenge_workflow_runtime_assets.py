from pathlib import Path

import pytest

from orket.orket import ConfigLoader
from orket.schema import EpicConfig, TeamConfig

pytestmark = pytest.mark.unit


def test_challenge_workflow_runtime_assets_load_from_repo() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    loader = ConfigLoader(repo_root)

    team = loader.load_asset("teams", "challenge_coder_guard_team", TeamConfig)
    epic = loader.load_asset("epics", "challenge_workflow_runtime", EpicConfig)

    assert sorted(team.seats.keys()) == ["coder", "integrity_guard"]
    assert epic.team == "challenge_coder_guard_team"
    assert epic.params["cards_runtime"]["scenario_truth"]["expected_terminal_status"] == "done"
    assert len(epic.issues) == 12
    assert all(issue.seat == "coder" for issue in epic.issues)
    assert sum(
        1 for issue in epic.issues if issue.params.get("execution_profile") == "build_app_v1"
    ) == 1
    assert epic.issues[-1].id == "CWR-12"

    issues = {issue.id: issue for issue in epic.issues}
    validator_semantics = issues["CWR-05"].params["artifact_contract"]["semantic_checks"][0]
    assert "task_ids = {task['id'] for task in workflow['tasks']}" in issues["CWR-05"].note
    assert "recognized as dependency_cycle rather than as an unknown dependency caused by one-pass ordering" in issues["CWR-05"].note
    assert "Track duplicate ids with a dedicated seen_ids or equivalent collection" in issues["CWR-05"].note
    assert "def validate_workflow(path: str)" in validator_semantics["must_contain"]
    assert "load_workflow(path)" in validator_semantics["must_contain"]
    assert "task_ids = {task['id'] for task in workflow['tasks']}" in validator_semantics["must_contain"]
    assert "seen_ids = set()" in validator_semantics["must_contain"]
    assert "if task['id'] in seen_ids:" in validator_semantics["must_contain"]
    assert "seen_ids.add(task['id'])" in validator_semantics["must_contain"]
    assert "task_graph = {task_id: [] for task_id in task_ids}" in validator_semantics["must_contain"]
    assert "if dep not in task_ids:" in validator_semantics["must_contain"]
    assert "task_graph[task['id']].append(dep)" in validator_semantics["must_contain"]
    assert "has_cycle" in validator_semantics["must_contain"]
    assert "if task['id'] in visited:" in validator_semantics["must_not_contain"]

    validator_verifier = issues["CWR-05"].params["runtime_verifier"]
    assert validator_verifier["commands"][0]["cwd"] == "agent_output"
    assert validator_verifier["json_assertions"] == [
        {"path": "has_dependency_cycle", "op": "eq", "value": True},
        {"path": "has_unknown_dependency", "op": "eq", "value": True},
        {"path": "has_duplicate_task_id", "op": "eq", "value": True},
    ]

    planner_semantics = issues["CWR-06"].params["artifact_contract"]["semantic_checks"][0]
    assert "task_ids = [task['id'] for task in workflow['tasks']]" in issues["CWR-06"].note
    assert "zero_in_degree = [task_id for task_id in task_ids if in_degree[task_id] == 0]" in issues["CWR-06"].note
    assert "for task_id in current_layer" in issues["CWR-06"].note
    assert "List[List[str]]" in planner_semantics["must_contain"]
    assert "def plan_workflow(path: str)" in planner_semantics["must_contain"]
    assert "load_workflow(path)" in planner_semantics["must_contain"]
    assert "task_ids = [task['id'] for task in workflow['tasks']]" in planner_semantics["must_contain"]
    assert "zero_in_degree = [task_id for task_id in task_ids if in_degree[task_id] == 0]" in planner_semantics["must_contain"]
    assert "for task_id in current_layer" in planner_semantics["must_contain"]
    assert "adjacency_list[dep].append(task['id'])" in planner_semantics["must_contain"]
    assert "in_degree[task['id']] += 1" in planner_semantics["must_contain"]
    assert "List[List[TaskSpec]]" in planner_semantics["must_not_contain"]
    assert "task_ids = {task['id'] for task in workflow['tasks']}" in planner_semantics["must_not_contain"]
    assert "for task_id in task_ids:" in planner_semantics["must_not_contain"]
    assert "queue.append(task)" in planner_semantics["must_not_contain"]
    assert "current_layer.append(task)" in planner_semantics["must_not_contain"]

    planner_verifier = issues["CWR-06"].params["runtime_verifier"]
    assert planner_verifier["commands"][0]["cwd"] == "agent_output"
    assert planner_verifier["json_assertions"] == [
        {"path": "layer_count", "op": "eq", "value": 3},
        {"path": "layer0.0", "op": "eq", "value": "task1"},
        {"path": "layer1.0", "op": "eq", "value": "task2"},
        {"path": "layer1.1", "op": "eq", "value": "task3"},
        {"path": "layer2.0", "op": "eq", "value": "task4"},
    ]

    valid_fixture_semantics = issues["CWR-03"].params["artifact_contract"]["semantic_checks"][0]
    assert "task2 and task3 both depend on task1" in issues["CWR-03"].note
    assert "task4 depends on both task2 and task3" in issues["CWR-03"].note
    assert "cycle fixture is exactly two tasks" in issues["CWR-03"].note
    assert "retry fixture is exactly one task named task1" in issues["CWR-03"].note
    assert "\"id\": \"task4\"" in valid_fixture_semantics["must_contain"]
    assert "\"deps\": [\"task1\"]" in valid_fixture_semantics["must_contain"]
    assert "\"deps\": [\"task2\", \"task3\"]" in valid_fixture_semantics["must_contain"]
    cycle_fixture_semantics = issues["CWR-03"].params["artifact_contract"]["semantic_checks"][1]
    assert "\"deps\": [\"task2\"]" in cycle_fixture_semantics["must_contain"]
    assert "\"deps\": [\"task1\"]" in cycle_fixture_semantics["must_contain"]
    assert "\"id\": \"task3\"" in cycle_fixture_semantics["must_not_contain"]
    retry_fixture_semantics = issues["CWR-03"].params["artifact_contract"]["semantic_checks"][2]
    assert "\"retries\": 1" in retry_fixture_semantics["must_contain"]
    assert "\"outcomes\": [\"failure\", \"success\"]" in retry_fixture_semantics["must_contain"]
    assert "\"id\": \"task2\"" in retry_fixture_semantics["must_not_contain"]
    fixture_verifier = issues["CWR-03"].params["runtime_verifier"]
    assert fixture_verifier["commands"][0]["cwd"] == "agent_output"
    assert fixture_verifier["json_assertions"] == [
        {"path": "task_count", "op": "eq", "value": 4},
        {"path": "task_ids.0", "op": "eq", "value": "task1"},
        {"path": "task_ids.1", "op": "eq", "value": "task2"},
        {"path": "task_ids.2", "op": "eq", "value": "task3"},
        {"path": "task_ids.3", "op": "eq", "value": "task4"},
        {"path": "task2_deps", "op": "eq", "value": ["task1"]},
        {"path": "task3_deps", "op": "eq", "value": ["task1"]},
        {"path": "task4_deps", "op": "eq", "value": ["task2", "task3"]},
    ]

    assert "self.workflow_path = workflow_path" in issues["CWR-07"].note
    assert "plan_workflow(self.workflow_path)" in issues["CWR-07"].note
    assert "for layer in layers" in issues["CWR-07"].note
    assert "ready_tasks = self.get_ready_tasks(layer)" in issues["CWR-07"].note
    assert "while ready_tasks" in issues["CWR-07"].note
    assert "retry budget must be reconsidered in the same layer" in issues["CWR-07"].note
    assert "Recompute ready_tasks for the same layer after each batch" in issues["CWR-07"].note
    assert "do not pop one task id and break out of the layer" in issues["CWR-07"].note
    assert "stop rerunning that unchanged blocked layer" in issues["CWR-07"].note
    assert "completed_task_ids" in issues["CWR-07"].note
    assert "task['duration']" in issues["CWR-07"].note
    assert "task['deps']" in issues["CWR-07"].note
    assert "task['retries'] + 1" in issues["CWR-07"].note
    assert "self.workflow['max_concurrency']" in issues["CWR-07"].note
    assert "self.workflow['tasks'][task_id]" in issues["CWR-07"].note
    assert "task['id'] == task_id" in issues["CWR-07"].note
    assert "any(dep not in self.completed_task_ids for dep in task['deps'])" in issues["CWR-07"].note

    simulator_verifier = issues["CWR-07"].params["runtime_verifier"]
    assert simulator_verifier["commands"][0]["cwd"] == "agent_output"
    assert simulator_verifier["json_assertions"] == [
        {"path": "retry_state", "op": "eq", "value": "completed"},
        {"path": "blocked_state", "op": "eq", "value": "blocked"},
        {"path": "downstream_ran", "op": "eq", "value": False},
        {"path": "retry_attempts", "op": "eq", "value": 2},
    ]
    simulator_semantics = issues["CWR-07"].params["artifact_contract"]["semantic_checks"][0]
    assert "def run_task" in simulator_semantics["must_contain"]
    assert "completed_task_ids" in simulator_semantics["must_contain"]
    assert "for layer in layers" in simulator_semantics["must_contain"]
    assert "ready_tasks = self.get_ready_tasks(layer)" in simulator_semantics["must_contain"]
    assert "batch = ready_tasks[:self.workflow['max_concurrency']]" in simulator_semantics["must_contain"]
    assert "self.run_task(task)" in simulator_semantics["must_contain"]
    assert "for task_id in layer" in simulator_semantics["must_contain"]
    assert "plan_workflow(self.workflow_path)" in simulator_semantics["must_contain"]
    assert "task['deps']" in simulator_semantics["must_contain"]
    assert "task['retries'] + 1" in simulator_semantics["must_contain"]
    assert "self.terminal_state = 'blocked'" in simulator_semantics["must_contain"]
    assert "self.workflow['max_concurrency']" in simulator_semantics["must_contain"]
    assert "task['duration']" in simulator_semantics["must_contain"]
    assert "attempt > len(task['outcomes'])" in simulator_semantics["must_not_contain"]
    assert "plan_workflow(self.workflow)" in simulator_semantics["must_not_contain"]
    assert "while layers:" in simulator_semantics["must_not_contain"]
    assert "self.get_ready_tasks(layers)" in simulator_semantics["must_not_contain"]
    assert "ready_tasks.pop(0)" in simulator_semantics["must_not_contain"]
    assert (
        "layers = [layer for layer in layers if any(task_id not in self.completed_task_ids for task_id in layer)]"
        in simulator_semantics["must_not_contain"]
    )
    assert "self.workflow['tasks'][task_id]" in simulator_semantics["must_not_contain"]
    assert (
        "ready_tasks = [task for task in self.workflow['tasks'] if task['id'] in layer and all(dep in self.completed_task_ids for dep in task['deps'])]"
        in simulator_semantics["must_not_contain"]
    )
    assert "any(dep in self.completed_task_ids for dep in task['deps'])" in simulator_semantics["must_not_contain"]
    assert "all(outcome == 'success' for event in self.event_log)" in simulator_semantics["must_not_contain"]

    checkpoint_verifier = issues["CWR-08"].params["runtime_verifier"]
    assert checkpoint_verifier["commands"][0]["cwd"] == "agent_output"
    assert checkpoint_verifier["json_assertions"] == [
        {"path": "checkpoint_loaded", "op": "eq", "value": True},
        {"path": "first_terminal_state", "op": "eq", "value": "completed"},
        {"path": "resumed_terminal_state", "op": "eq", "value": "completed"},
    ]

    main_semantics = issues["CWR-09"].params["artifact_contract"]["semantic_checks"][1]
    assert "validated_count counts proof validations performed" in issues["CWR-09"].note
    assert "cycle fixture must still contribute to validated_count" in issues["CWR-09"].note
    assert "validated_count = 2" in issues["CWR-09"].note
    assert "dependency_cycle = any(error['code'] == 'dependency_cycle' for error in cycle_errors)" in issues["CWR-09"].note
    assert "do not derive it from len(valid_errors)" in issues["CWR-09"].note
    assert "from challenge_runtime" in main_semantics["must_contain"]
    assert "from challenge_runtime.validator import validate_workflow" in main_semantics["must_contain"]
    assert "from challenge_runtime.planner import plan_workflow" in main_semantics["must_contain"]
    assert "from challenge_runtime.simulator import Simulator" in main_semantics["must_contain"]
    assert "from challenge_runtime.checkpoint import save_checkpoint, resume_simulation" in main_semantics["must_contain"]
    assert "os.path.dirname(os.path.abspath(__file__))" in main_semantics["must_contain"]
    assert "valid_errors = validate_workflow(workflow_valid_path)" in main_semantics["must_contain"]
    assert "cycle_errors = validate_workflow(workflow_cycle_path)" in main_semantics["must_contain"]
    assert "validated_count = 2" in main_semantics["must_contain"]
    assert "dependency_cycle" in main_semantics["must_contain"]
    assert "dependency_cycle = any(error['code'] == 'dependency_cycle' for error in cycle_errors)" in main_semantics["must_contain"]
    assert "plan_workflow(workflow_valid_path)" in main_semantics["must_contain"]
    assert "workflow_retry.json" in main_semantics["must_contain"]
    assert "plan_workflow(workflow_valid)" in main_semantics["must_not_contain"]
    assert "validated_count = len(valid_errors)" in main_semantics["must_not_contain"]
    assert "validated_count = len(valid_errors) + 1" in main_semantics["must_not_contain"]
    assert "agent_output/challenge_inputs/" in main_semantics["must_not_contain"]
    assert "from .challenge_runtime" in main_semantics["must_not_contain"]

    cli_semantics = issues["CWR-09"].params["artifact_contract"]["semantic_checks"][0]
    assert "add_argument('path'" in cli_semantics["must_contain"]
    assert "args.path" in cli_semantics["must_contain"]
    assert "add_argument('args.path'" in cli_semantics["must_not_contain"]
    assert "args.args.path" in cli_semantics["must_not_contain"]
    assert "workflow_valid.json" in cli_semantics["must_not_contain"]
    assert "workflow_cycle.json" in cli_semantics["must_not_contain"]
    assert "workflow_retry.json" in cli_semantics["must_not_contain"]

    validator_test_semantics = issues["CWR-10"].params["artifact_contract"]["semantic_checks"][0]
    assert "Use tmp_path to create the duplicate-id and unknown-dependency workflow files" in issues["CWR-10"].note
    assert "dependency-cycle test must validate the shipped workflow_cycle.json" in issues["CWR-10"].note
    assert "must use the shipped branched workflow_valid.json from challenge_inputs" in issues["CWR-10"].note
    assert "Import validate_workflow and plan_workflow explicitly" in issues["CWR-10"].note
    assert "layers[1] == ['task2', 'task3']" in issues["CWR-10"].note
    assert "layers[2] == ['task4']" in issues["CWR-10"].note
    assert "import json" in validator_test_semantics["must_contain"]
    assert "from pathlib import Path" in validator_test_semantics["must_contain"]
    assert "from challenge_runtime.validator import validate_workflow" in validator_test_semantics["must_contain"]
    assert "from challenge_runtime.planner import plan_workflow" in validator_test_semantics["must_contain"]
    assert "Path(__file__).resolve().parents[1] / 'challenge_inputs'" in validator_test_semantics["must_contain"]
    assert "Path(__file__).resolve().parents[1] / 'challenge_inputs' / 'workflow_cycle.json'" in validator_test_semantics["must_contain"]
    assert "Path(__file__).resolve().parents[1] / 'challenge_inputs' / 'workflow_valid.json'" in validator_test_semantics["must_contain"]
    assert "tmp_path" in validator_test_semantics["must_contain"]
    assert "tmp_path / 'workflow_duplicate.json'" in validator_test_semantics["must_contain"]
    assert "tmp_path / 'workflow_unknown_dependency.json'" in validator_test_semantics["must_contain"]
    assert "write_text(json.dumps(" in validator_test_semantics["must_contain"]
    assert "duplicate_task_id" in validator_test_semantics["must_contain"]
    assert "unknown_dependency" in validator_test_semantics["must_contain"]
    assert "dependency_cycle" in validator_test_semantics["must_contain"]
    assert "any(error['code'] == 'dependency_cycle' for error in errors)" in validator_test_semantics["must_contain"]
    assert "layers[1] == ['task2', 'task3']" in validator_test_semantics["must_contain"]
    assert "layers[2] == ['task4']" in validator_test_semantics["must_contain"]
    assert "Path(__file__).parent / 'challenge_inputs'" in validator_test_semantics["must_not_contain"]
    assert "tmp_path / 'workflow_valid.json'" in validator_test_semantics["must_not_contain"]
    assert "challenge_inputs' / 'workflow_duplicate.json'" in validator_test_semantics["must_not_contain"]
    assert "challenge_inputs' / 'workflow_unknown_dependency.json'" in validator_test_semantics["must_not_contain"]

    validator_test_verifier = issues["CWR-10"].params["runtime_verifier"]
    assert validator_test_verifier["commands"] == [
        {"argv": ["python", "-m", "pytest", "-q", "tests/test_validator_and_planner.py"], "cwd": "agent_output"}
    ]

    simulator_test_semantics = issues["CWR-11"].params["artifact_contract"]["semantic_checks"][0]
    assert "The retry fixture succeeds with terminal state 'completed'" in issues["CWR-11"].note
    assert "artifact_root = Path(__file__).resolve().parents[1] / 'challenge_artifacts'" in issues["CWR-11"].note
    assert "checkpoint_path = artifact_root / 'retry_checkpoint.json'" in issues["CWR-11"].note
    assert "tmp_path / 'workflow_dependency_gating.json'" in issues["CWR-11"].note
    assert "Use blocked fixture task ids named upstream and downstream" in issues["CWR-11"].note
    assert "make upstream fail with outcomes ['failure']" in issues["CWR-11"].note
    assert "downstream never appears in the event_log" in issues["CWR-11"].note
    assert "import json" in simulator_test_semantics["must_contain"]
    assert "save_checkpoint" in simulator_test_semantics["must_contain"]
    assert "load_checkpoint" in simulator_test_semantics["must_contain"]
    assert "Path(__file__).resolve().parents[1] / 'challenge_inputs'" in simulator_test_semantics["must_contain"]
    assert "Path(__file__).resolve().parents[1] / 'challenge_artifacts'" in simulator_test_semantics["must_contain"]
    assert "artifact_root = Path(__file__).resolve().parents[1] / 'challenge_artifacts'" in simulator_test_semantics["must_contain"]
    assert "artifact_root.mkdir(parents=True, exist_ok=True)" in simulator_test_semantics["must_contain"]
    assert "checkpoint_path = artifact_root / 'retry_checkpoint.json'" in simulator_test_semantics["must_contain"]
    assert "retry_checkpoint.json" in simulator_test_semantics["must_contain"]
    assert "terminal_state == 'completed'" in simulator_test_semantics["must_contain"]
    assert "resumed_terminal_state == 'completed'" in simulator_test_semantics["must_contain"]
    assert "loaded_checkpoint['terminal_state'] == 'completed'" in simulator_test_semantics["must_contain"]
    assert "loaded_checkpoint['event_log']" in simulator_test_semantics["must_contain"]
    assert "tmp_path / 'workflow_dependency_gating.json'" in simulator_test_semantics["must_contain"]
    assert "write_text(json.dumps(" in simulator_test_semantics["must_contain"]
    assert "'upstream'" in simulator_test_semantics["must_contain"]
    assert "'outcomes': ['failure']" in simulator_test_semantics["must_contain"]
    assert "not any(event['task_id'] == 'downstream'" in simulator_test_semantics["must_contain"]
    assert "'downstream'" in simulator_test_semantics["must_contain"]
    assert "blocked" in simulator_test_semantics["must_contain"]
    assert "challenge_artifacts" in simulator_test_semantics["must_contain"]
    assert "Path(__file__).parent / 'challenge_inputs'" in simulator_test_semantics["must_not_contain"]
    assert "agent_output/challenge_inputs/" in simulator_test_semantics["must_not_contain"]
    assert "checkpoint_path = tmp_path /" in simulator_test_semantics["must_not_contain"]
    assert "== 'success'" in simulator_test_semantics["must_not_contain"]

    simulator_test_verifier = issues["CWR-11"].params["runtime_verifier"]
    assert simulator_test_verifier["commands"] == [
        {"argv": ["python", "-m", "pytest", "-q", "tests/test_simulator_and_resume.py"], "cwd": "agent_output"}
    ]

    reporting_semantics = issues["CWR-12"].params["artifact_contract"]["semantic_checks"][0]
    assert "import json" in reporting_semantics["must_contain"]
    assert "def format_report" in reporting_semantics["must_contain"]

    verifier_contract = issues["CWR-12"].params["runtime_verifier"]
    assert verifier_contract["commands"] == [
        {"argv": ["python", "-m", "pytest", "-q", "tests"], "cwd": "agent_output"},
        {
            "argv": [
                "python",
                "-c",
                "import json; from challenge_runtime.reporting import format_report; rendered = format_report({'ok': True}); payload = json.loads(rendered); print(json.dumps(payload))",
            ],
            "cwd": "agent_output",
        },
        {"argv": ["python", "agent_output/main.py"], "cwd": "."},
    ]
    assert verifier_contract["json_assertions"][0]["path"] == "validated_count"
