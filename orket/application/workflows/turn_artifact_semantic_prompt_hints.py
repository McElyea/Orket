from __future__ import annotations

from typing import Iterable


def _normalized_tokens(values: Iterable[str]) -> set[str]:
    return {str(value).strip() for value in values if str(value).strip()}


def artifact_semantic_exact_shape_hints(
    *,
    path: str,
    must_contain: Iterable[str],
    must_not_contain: Iterable[str],
) -> list[str]:
    normalized_path = str(path).strip().replace("\\", "/")
    required_tokens = _normalized_tokens(must_contain)
    forbidden_tokens = _normalized_tokens(must_not_contain)

    if normalized_path.endswith("challenge_runtime/simulator.py"):
        required_loop_tokens = {
            "for layer in layers",
            "ready_tasks = self.get_ready_tasks(layer)",
            "batch = ready_tasks[:self.workflow['max_concurrency']]",
            "self.run_task(task)",
            "task['retries'] + 1",
        }
        if required_loop_tokens.issubset(required_tokens):
            return [
                "- Keep the planner loop in this exact layer-driven form: layers = plan_workflow(self.workflow_path); for layer in layers: ready_tasks = self.get_ready_tasks(layer)",
                "- When batching ready tasks, batch contains task dicts, not task ids.",
                "- Use this exact batch loop verbatim: batch = ready_tasks[:self.workflow['max_concurrency']]; for task in batch: self.run_task(task)",
                "- Keep the ready-task retry guard as this exact substring verbatim: self.attempt_counts.get(task['id'], 0) < task['retries'] + 1",
                "- Do not replace layers with self.layers, and do not replace task with task_id in self.run_task(...).",
            ]

    if normalized_path.endswith("tests/test_validator_and_planner.py"):
        required_fixture_tokens = {
            "Path(__file__).resolve().parents[1] / 'challenge_inputs' / 'workflow_cycle.json'",
            "Path(__file__).resolve().parents[1] / 'challenge_inputs' / 'workflow_valid.json'",
            "write_text(json.dumps(",
        }
        if required_fixture_tokens.issubset(required_tokens) and "tmp_path / 'workflow_valid.json'" in forbidden_tokens:
            return [
                "- Use shipped fixtures exactly like this: workflow_cycle_path = Path(__file__).resolve().parents[1] / 'challenge_inputs' / 'workflow_cycle.json' and workflow_valid_path = Path(__file__).resolve().parents[1] / 'challenge_inputs' / 'workflow_valid.json'",
                "- Only duplicate and unknown-dependency cases use tmp_path: workflow_path = tmp_path / 'workflow_duplicate.json' or workflow_path = tmp_path / 'workflow_unknown_dependency.json'",
                "- Keep this exact write pattern for temporary workflow files: workflow_path.write_text(json.dumps(workflow), encoding='utf-8')",
                "- Never create or validate tmp_path / 'workflow_valid.json'.",
            ]

    if normalized_path.endswith("tests/test_simulator_and_resume.py"):
        required_resume_tokens = {
            "def test_simulator_and_resume(tmp_path):",
            "from challenge_runtime.simulator import Simulator",
            "from challenge_runtime.checkpoint import save_checkpoint, load_checkpoint, resume_simulation",
            "Path(__file__).resolve().parents[1] / 'challenge_inputs' / 'workflow_retry.json'",
            "artifact_root = Path(__file__).resolve().parents[1] / 'challenge_artifacts'",
            "checkpoint_path = artifact_root / 'retry_checkpoint.json'",
            "resumed_terminal_state == 'completed'",
            "resumed_again_terminal_state == 'completed'",
            "tmp_path / 'workflow_dependency_gating.json'",
            "write_text(json.dumps(",
        }
        if required_resume_tokens.issubset(required_tokens):
            return [
                "- Keep tmp_path as the real pytest fixture by using this exact test signature: def test_simulator_and_resume(tmp_path):. Do not reassign tmp_path to a repo-local Path.",
                "- Keep the imports split exactly like this: from challenge_runtime.simulator import Simulator and from challenge_runtime.checkpoint import save_checkpoint, load_checkpoint, resume_simulation. Do not import checkpoint helpers from challenge_runtime.simulator.",
                "- Use the shipped retry fixture exactly like this: workflow_retry_path = Path(__file__).resolve().parents[1] / 'challenge_inputs' / 'workflow_retry.json'; simulator = Simulator(str(workflow_retry_path)); terminal_state = simulator.simulate(); assert terminal_state == 'completed'.",
                "- Use package-root artifacts exactly like this: artifact_root = Path(__file__).resolve().parents[1] / 'challenge_artifacts'; artifact_root.mkdir(parents=True, exist_ok=True); checkpoint_path = artifact_root / 'retry_checkpoint.json'.",
                "- After resuming, keep these exact variable/assertion shapes: resumed = resume_simulation(str(checkpoint_path)); resumed_terminal_state = resumed.terminal_state; assert resumed_terminal_state == 'completed'.",
                "- Keep the second resume in this exact form: resumed_again = resume_simulation(str(checkpoint_path)); resumed_again_terminal_state = resumed_again.terminal_state; assert resumed_again_terminal_state == 'completed'.",
                "- Only the dependency-gating fixture uses pytest tmp_path, and it must use this exact blocked-workflow shape: workflow = {'workflow_id': 'dependency_gating_workflow', 'max_concurrency': 1, 'tasks': [{'id': 'upstream', 'deps': [], 'duration': 5, 'retries': 0, 'outcomes': ['failure']}, {'id': 'downstream', 'deps': ['upstream'], 'duration': 5, 'retries': 1, 'outcomes': ['success']}]}; dependency_gating_path = tmp_path / 'workflow_dependency_gating.json'; dependency_gating_path.write_text(json.dumps(workflow), encoding='utf-8').",
                "- Keep the blocked assertion exact: terminal_state = simulator.simulate(); assert terminal_state == 'blocked'; assert not any(event['task_id'] == 'downstream' for event in simulator.event_log).",
                "- Do not invent a repo-local tmp directory under Path(__file__).resolve().parents[1] / 'tmp'.",
            ]

    if normalized_path.endswith("challenge_runtime/models.py"):
        required_model_tokens = {
            "from typing import List, TypedDict",
            "class TaskSpec(TypedDict):",
            "class WorkflowSpec(TypedDict):",
            "tasks: List[TaskSpec]",
        }
        if required_model_tokens.issubset(required_tokens):
            return [
                "- In challenge_runtime/models.py, define the schema names as TypedDict mappings with this exact import: from typing import List, TypedDict.",
                "- Keep TaskSpec limited to task-level fields only: id, deps, duration, retries, outcomes.",
                "- Keep WorkflowSpec limited to root-level fields only: workflow_id, max_concurrency, tasks: List[TaskSpec].",
                "- Do not repeat workflow root fields inside TaskSpec, and do not repeat task-level fields as top-level WorkflowSpec members.",
            ]

    if normalized_path.endswith("challenge_runtime/loader.py"):
        required_normalization_tokens = {
            "from .models import TaskSpec, WorkflowSpec",
            "json.load(",
            "def load_workflow(path: str) -> WorkflowSpec:",
            "def normalize_task(raw_task) -> TaskSpec:",
            "'tasks': [normalize_task(task) for task in data['tasks']]",
        }
        if required_normalization_tokens.issubset(required_tokens):
            return [
                "- In challenge_runtime/loader.py, import the schema names before using them in annotations or constructors: from .models import TaskSpec, WorkflowSpec.",
                "- Return mapping-shaped workflow data so downstream code can use workflow['tasks'] and task['id'] directly.",
                "- Keep normalize_task in this exact field-copy form: return {'id': raw_task['id'], 'deps': raw_task['deps'], 'duration': raw_task['duration'], 'retries': raw_task['retries'], 'outcomes': raw_task['outcomes']}.",
                "- Keep load_workflow in this exact normalization form: return {'workflow_id': data['workflow_id'], 'max_concurrency': data['max_concurrency'], 'tasks': [normalize_task(task) for task in data['tasks']]}.",
                "- Do not call WorkflowSpec(**data) or TaskSpec(**raw_task), and never import through agent_output.challenge_runtime.",
            ]

        required_loader_tokens = {
            "json.load(",
            "def load_workflow",
            "def normalize_task",
            "from .models import TaskSpec, WorkflowSpec",
        }
        if required_loader_tokens.issubset(required_tokens):
            return [
                "- In challenge_runtime/loader.py, import the schema names before using them in annotations or constructors: from .models import TaskSpec, WorkflowSpec.",
                "- Keep package-local imports inside challenge_runtime modules; never import through agent_output.challenge_runtime.",
            ]

    if normalized_path.endswith("challenge_runtime/__init__.py"):
        required_export_tokens = {
            "from .models import TaskSpec, WorkflowSpec",
            "from .loader import load_workflow, normalize_task",
        }
        if required_export_tokens.issubset(required_tokens):
            return [
                "- In challenge_runtime/__init__.py, export the admitted public names with these exact imports: from .models import TaskSpec, WorkflowSpec and from .loader import load_workflow, normalize_task.",
                "- Do not leave challenge_runtime/__init__.py empty.",
            ]

    if normalized_path.endswith("challenge_runtime/validator.py"):
        required_validator_tokens = {
            "def validate_workflow(path: str)",
            "load_workflow(path)",
            "from .loader import load_workflow",
            "from .models import WorkflowSpec, TaskSpec",
        }
        if required_validator_tokens.issubset(required_tokens):
            return [
                "- Inside package modules under challenge_runtime, import sibling modules with package-local imports such as from .loader import load_workflow and from .models import WorkflowSpec, TaskSpec.",
                "- Never import through agent_output.challenge_runtime inside generated package files.",
            ]

    if normalized_path.endswith("challenge_runtime/planner.py"):
        required_planner_tokens = {
            "task_ids = [task['id'] for task in workflow['tasks']]",
            "zero_in_degree = [task_id for task_id in task_ids if in_degree[task_id] == 0]",
            "for task_id in current_layer",
            "adjacency_list[dep].append(task['id'])",
            "in_degree[task['id']] += 1",
        }
        if required_planner_tokens.issubset(required_tokens):
            return [
                "- In challenge_runtime/planner.py, build task_ids, adjacency_list, and in_degree first, then scan workflow['tasks'] to append adjacency_list[dep].append(task['id']) and increment in_degree[task['id']].",
                "- Compute zero_in_degree only after that dependency scan: zero_in_degree = [task_id for task_id in task_ids if in_degree[task_id] == 0]. Do not compute it before filling in_degree.",
                "- Keep the layer loop in task-id space: while zero_in_degree: current_layer = zero_in_degree; zero_in_degree = []; for task_id in current_layer: ...",
                "- The branched valid workflow must plan as three layers ['task1'], ['task2', 'task3'], ['task4']; do not place every task in the first layer.",
            ]

    return []
