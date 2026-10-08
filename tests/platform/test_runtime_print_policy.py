import ast
from pathlib import Path

import pytest

from scripts.common.git_inventory import git_list_files

pytestmark = pytest.mark.unit


def _print_lines(source: str) -> list[int]:
    return sorted(
        node.lineno for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and (
            isinstance(node.func, ast.Name) and node.func.id == "print"
            or isinstance(node.func, ast.Attribute) and node.func.attr == "print"
        )
    )


@pytest.mark.parametrize(("source", "expected"), [
    ("print('application output')", [1]),
    ("builtins.print('application output')", [1]),
    ("console.print('application output')", [1]),
    ('''probe = "print('captured child output')"''', []),
    ("# print('comment only')", []),
    ('''probe = "print('captured child output')"\nprint('application output')''', [2]),
])
def test_print_policy_distinguishes_calls_from_source_text(source, expected):
    """Layer: unit. Real calls remain visible beside embedded command source."""
    assert _print_lines(source) == expected


def test_runtime_print_usage_is_whitelisted():
    """
    Layer: unit. Static output-boundary check; not runtime execution proof.
    Guardrail: runtime/library modules should use structured logging.
    `print()` is only allowed in explicitly interactive/intentional files.
    """
    repo_root = Path(__file__).resolve().parents[2]
    orket_root = repo_root / "orket"
    assert orket_root.exists(), f"Expected runtime package root at {orket_root}"

    allowed_files = {
        "orket/interfaces/cli.py",
        "orket/interfaces/setup_cli.py",
        "orket/discovery.py",
        # Verification subprocess contract writes JSON to stdout by design.
        "orket/domain/verification.py",
        # Standalone utility script with direct console output.
        "orket/orchestration/project_dumper_small.py",
        # Explicit command-line surfaces with direct user output.
        "orket/cli.py",
        "orket/interfaces/doctor_cli.py",
        "orket/interfaces/local_agent_example_cli.py",
        "orket/interfaces/governed_agent_cli.py",
        "orket/interfaces/orket_bundle_cli.py",
        "orket/interfaces/bundle_outward_cli.py",
        "orket/interfaces/bundle_cli_output.py",
        "orket/interfaces/outward_authority_cli.py",
        "orket/interfaces/prompts_cli.py",
        "orket/interfaces/runtime_store_cli.py",
        "orket/quickstart/governed_action_demo.py",
    }

    violations = []
    for py_file in git_list_files(repo_root):
        if py_file.suffix != ".py" or not py_file.is_relative_to(orket_root):
            continue
        rel = py_file.relative_to(repo_root).as_posix()
        if rel in allowed_files:
            continue
        source = py_file.read_text(encoding="utf-8-sig")
        violations.extend(f"{rel}:{lineno}" for lineno in _print_lines(source))

    assert not violations, "Disallowed print() usage found:\n" + "\n".join(violations)
