# Layer: unit

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = (
    REPO_ROOT / "orket",
    REPO_ROOT / "scripts",
)
WORKLOAD_AUTHORITY_MATRIX_DOC = (
    REPO_ROOT / "docs" / "projects" / "ControlPlane" / "CONTROL_PLANE_CONVERGENCE_WORKSTREAM_1_CLOSEOUT.md"
)
ALLOWED_PATHS = {
    REPO_ROOT / "orket" / "application" / "services" / "control_plane_workload_catalog.py",
    REPO_ROOT / "orket" / "core" / "contracts" / "workload_identity.py",
    REPO_ROOT / "orket" / "core" / "contracts" / "__init__.py",
}
LOW_LEVEL_BUILDERS = {
    "build_control_plane_workload_record",
    "build_control_plane_workload_record_from_workload_contract",
}
WORKLOAD_AUTHORITY_IMPORTS = {
    "GITEA_STATE_WORKER_EXECUTION_WORKLOAD",
    "KERNEL_ACTION_WORKLOAD",
    "ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD",
    "ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD",
    "ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD",
    "REVIEW_RUN_WORKLOAD",
    "TURN_TOOL_WORKLOAD",
    "control_plane_workload_for_key",
    "resolve_control_plane_workload",
    "sandbox_runtime_workload_for_tech_stack",
}
EXPECTED_GOVERNED_START_PATH_MATRIX = {
    "cards epic execution": {
        "status": "projection-resolved",
        "paths": {"orket/runtime/execution_pipeline.py"},
    },
    "ODR / run arbiter": {
        "status": "projection-resolved",
        "paths": {"scripts/odr/run_arbiter.py"},
    },
    "manual review-run": {
        "status": "catalog-resolved",
        "paths": {"orket/application/services/review_run_control_plane_service.py"},
    },
    "sandbox runtime": {
        "status": "catalog-resolved",
        "paths": {
            "orket/application/services/sandbox_control_plane_execution_service.py",
            "orket/services/sandbox_orchestrator.py",
        },
    },
    "kernel action": {
        "status": "catalog-resolved",
        "paths": {"orket/application/services/kernel_action_control_plane_service.py"},
    },
    "governed turn-tool": {
        "status": "catalog-resolved",
        "paths": {"orket/application/services/turn_tool_control_plane_service.py"},
    },
    "orchestrator issue dispatch": {
        "status": "catalog-resolved",
        "paths": {"orket/application/services/orchestrator_issue_control_plane_service.py"},
    },
    "orchestrator scheduler mutation": {
        "status": "catalog-resolved",
        "paths": {"orket/application/services/orchestrator_scheduler_control_plane_service.py"},
    },
    "orchestrator child workload composition": {
        "status": "catalog-resolved",
        "paths": {"orket/application/services/orchestrator_scheduler_control_plane_service.py"},
    },
    "Gitea state worker": {
        "status": "catalog-resolved",
        "paths": {"orket/application/services/gitea_state_control_plane_execution_service.py"},
    },
    "extension workload execution": {
        "status": "projection-resolved",
        "paths": {"orket/extensions/manager.py"},
    },
    "rock entrypoints that initiate governed execution": {
        "status": "delegated",
        "paths": {"orket/runtime/execution_pipeline.py"},
    },
}
CATALOG_RESOLVED_IDENTITY_ALIAS_BANS = {
    "orket/application/services/gitea_state_control_plane_execution_service.py": {
        "WORKLOAD_ID",
        "WORKLOAD_VERSION",
    },
    "orket/application/services/kernel_action_control_plane_service.py": {
        "WORKLOAD_ID",
        "WORKLOAD_VERSION",
    },
    "orket/application/services/orchestrator_issue_control_plane_service.py": {
        "WORKLOAD_ID",
        "WORKLOAD_VERSION",
    },
    "orket/application/services/orchestrator_scheduler_control_plane_service.py": {
        "TRANSITION_WORKLOAD_ID",
        "TRANSITION_WORKLOAD_VERSION",
        "CHILD_WORKLOAD_ID",
        "CHILD_WORKLOAD_VERSION",
    },
    "orket/application/services/review_run_control_plane_service.py": {
        "WORKLOAD_ID",
        "WORKLOAD_VERSION",
    },
    "orket/application/services/turn_tool_control_plane_service.py": {
        "WORKLOAD_ID",
        "WORKLOAD_VERSION",
    },
}


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        files.extend(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)
    return sorted(files)


def _relative_path(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _builder_violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported = sorted(
                alias.name
                for alias in node.names
                if alias.name in LOW_LEVEL_BUILDERS
            )
            if imported:
                violations.append(f"import:{','.join(imported)}")
            continue
        if isinstance(node, ast.Call):
            target = ""
            if isinstance(node.func, ast.Name):
                target = node.func.id
            elif isinstance(node.func, ast.Attribute):
                target = node.func.attr
            if target in LOW_LEVEL_BUILDERS:
                violations.append(f"call:{target}")
    return sorted(set(violations))


def _parse_workload_authority_matrix() -> dict[str, str]:
    text = WORKLOAD_AUTHORITY_MATRIX_DOC.read_text(encoding="utf-8")
    start_marker = "The current workload-authority matrix for governed start paths is:"
    end_marker = "## Surviving projection-only or still-temporary surfaces"
    section = text.split(start_marker, 1)[1].split(end_marker, 1)[0]
    rows: dict[str, str] = {}
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        parts = [part.strip() for part in stripped.strip("|").split("|")]
        if len(parts) != 3:
            continue
        start_path, status, truthful_note = parts
        if start_path == "Start path" or start_path == "---" or status == "---" or truthful_note == "---":
            continue
        rows[start_path] = status.strip("`")
    return rows


def _catalog_authority_consumer_paths() -> set[str]:
    consumers: set[str] = set()
    for path in _iter_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module != "orket.application.services.control_plane_workload_catalog":
                continue
            imported = {alias.name for alias in node.names}
            if imported & WORKLOAD_AUTHORITY_IMPORTS:
                consumers.add(_relative_path(path))
                break
    return consumers


def _load_execution_pipeline_method(method_name: str) -> ast.AsyncFunctionDef | ast.FunctionDef:
    path = REPO_ROOT / "orket" / "runtime" / "execution_pipeline.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "ExecutionPipeline":
            continue
        for child in node.body:
            if isinstance(child, (ast.AsyncFunctionDef, ast.FunctionDef)) and child.name == method_name:
                return child
    raise AssertionError(f"ExecutionPipeline.{method_name} not found")


def _class_assignment_targets(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    targets: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for child in node.body:
            if not isinstance(child, ast.Assign):
                continue
            for target in child.targets:
                if isinstance(target, ast.Name):
                    targets.add(target.id)
    return targets


def _call_targets(node: ast.AST) -> set[str]:
    targets: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if isinstance(child.func, ast.Name):
            targets.add(child.func.id)
        elif isinstance(child.func, ast.Attribute):
            targets.add(child.func.attr)
    return targets


def test_only_workload_authority_seam_mints_control_plane_workload_records() -> None:
    violations: dict[str, list[str]] = {}
    for path in _iter_python_files():
        if path in ALLOWED_PATHS:
            continue
        hits = _builder_violations(path)
        if hits:
            violations[_relative_path(path)] = hits
    assert violations == {}


def test_governed_start_path_matrix_stays_classified_and_exact() -> None:
    matrix = _parse_workload_authority_matrix()
    expected_statuses = {
        start_path: meta["status"] for start_path, meta in EXPECTED_GOVERNED_START_PATH_MATRIX.items()
    }
    assert matrix == expected_statuses


def test_only_matrix_covered_modules_consume_catalog_workload_authority() -> None:
    expected_paths = {
        path
        for meta in EXPECTED_GOVERNED_START_PATH_MATRIX.values()
        for path in meta["paths"]
    }
    assert _catalog_authority_consumer_paths() == expected_paths


def test_catalog_resolved_publishers_do_not_restate_workload_identity_as_string_aliases() -> None:
    violations = {
        relative_path: sorted(
            _class_assignment_targets(REPO_ROOT / relative_path) & banned_assignments
        )
        for relative_path, banned_assignments in CATALOG_RESOLVED_IDENTITY_ALIAS_BANS.items()
        if _class_assignment_targets(REPO_ROOT / relative_path) & banned_assignments
    }
    assert violations == {}


def test_run_rock_remains_delegated_until_ce01_closes() -> None:
    call_targets = _call_targets(_load_execution_pipeline_method("run_rock"))

    assert "run_epic" in call_targets
    assert {
        "build_control_plane_workload_record",
        "build_control_plane_workload_record_from_workload_contract",
        "control_plane_workload_for_key",
        "resolve_control_plane_workload",
        "sandbox_runtime_workload_for_tech_stack",
    }.isdisjoint(call_targets)
