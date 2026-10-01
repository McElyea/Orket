"""Actual setup fixtures and native holds; no synthetic filesystem results."""
from __future__ import annotations

import asyncio
import tomllib
from pathlib import Path
from types import SimpleNamespace

from orket.application.services.dependency_manager import DependencyValidationError
from orket.application.services.deployment_planner import DeploymentValidationError
from orket.application.services.orchestrator_support_services import OrchestratorSupportServices
from orket.application.services.scaffolder import Scaffolder, ScaffoldValidationError
from tests.helpers.evidence_ownership import hold_native_call
from tests.helpers.governed_read_ownership import interrupt_held_read
from tests.helpers.runtime_verification_hold import hold_stream

FILES = {
    "scaffolder": ("agent_output/files/first.txt", "agent_output/files/second.txt"),
    "dependency_manager": ("agent_output/dependencies/pyproject.toml", "agent_output/dependencies/requirements.txt",
                           "agent_output/dependencies/requirements-dev.txt"),
    "deployment_planner": ("agent_output/deployment/first.txt", "agent_output/deployment/second.txt"),
}
VALIDATION_ERRORS = {
    "scaffolder": ScaffoldValidationError,
    "dependency_manager": DependencyValidationError,
    "deployment_planner": DeploymentValidationError,
}


def setup_rules():
    return {
        "scaffolder_required_directories": ["agent_output/dirs"],
        "scaffolder_required_files": dict(zip(FILES["scaffolder"], ("original first", "original second"), strict=True)),
        "scaffolder_forbidden_extensions": [".bad"],
        "scaffolder_scan_roots": ["agent_output/scan"],
        "dependency_manager_stack_profile": "python",
        "dependency_manager_python_dependencies": ["fixture-lib==1.0"],
        "deployment_planner_required_files": dict(zip(FILES["deployment_planner"],
                                                      ("original first", "original second"), strict=True)),
    }


def prepare_tree(root, *, scan=True):
    root.mkdir(parents=True, exist_ok=True)
    if scan:
        directory = root / "agent_output/scan"
        directory.mkdir(parents=True)
        (directory / "existing.txt").write_text("existing operator file", encoding="utf-8")


async def make_stage(family, root):
    await asyncio.to_thread(prepare_tree, root, scan=family == "scaffolder")
    services = OrchestratorSupportServices()
    return getattr(services, "create_" + family)(
        workspace_root=root, organization=SimpleNamespace(process_rules=setup_rules()),
        project_surface_profile="unspecified", architecture_pattern="monolith")


def first_boundary(family):
    return "agent_output/dirs" if family == "scaffolder" else FILES[family][0]


def hold_metadata(monkeypatch, operation, target, *, suffix=False, failure=None):
    def selected(path):
        return tuple(path.parts[-len(target.parts):]) == target.parts if suffix else path == target

    if operation == "scan":
        hold = hold_native_call(monkeypatch, Scaffolder, "_collect_files", selected)
        monkeypatch.setattr(Scaffolder, "_collect_files", staticmethod(Scaffolder._collect_files))
        return hold
    if failure is not None:
        original = getattr(Path, operation)

        def fail_after_native(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if selected(path):
                raise failure
            return result

        monkeypatch.setattr(Path, operation, fail_after_native)
    return hold_native_call(monkeypatch, Path, operation, lambda path, *_args, **_kwargs: selected(path))


def hold_setup_stream(monkeypatch, path, operation):
    hold = hold_stream(monkeypatch, path, operation)
    # The shared stream helper's watchdog raises directly; the interruption helper
    # also accepts the metadata helper's explicit expiration observation.
    hold.expired = False
    return hold


async def interrupt_setup(task, hold, mode, database, record_property):
    return await interrupt_held_read(task, hold, mode, database, record_property)


def tree_contents(root):
    return {path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
            for path in root.rglob("*") if path.is_file()}


async def assert_completed(family, root):
    contents = await asyncio.to_thread(tree_contents, root)
    expected = set(FILES[family])
    if family == "scaffolder":
        expected.add("agent_output/scan/existing.txt")
        assert contents["agent_output/scan/existing.txt"] == "existing operator file"
        assert await asyncio.to_thread((root / "agent_output/dirs").is_dir)
    assert set(contents) == expected
    first, second = (contents[name] for name in FILES[family][:2])
    if family == "dependency_manager":
        assert tomllib.loads(first)["project"]["dependencies"] == ["fixture-lib==1.0"]
        assert second == "fixture-lib==1.0\n"
        assert contents[FILES[family][2]] == ""
    else:
        assert (first, second) == ("original first", "original second")


def assert_closed(hold):
    assert hold.finished.is_set() and not hold.expired
    if hasattr(hold, "streams"):
        assert hold.streams and all(stream.closed for stream in hold.streams)
