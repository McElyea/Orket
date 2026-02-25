from pathlib import Path
import re


def test_runtime_print_usage_is_whitelisted():
    """
    Guardrail: runtime/library modules should use structured logging.
    `print()` is only allowed in explicitly interactive/intentional files.
    """
    repo_root = Path(__file__).resolve().parents[2]
    orket_root = repo_root / "orket"
    assert orket_root.exists(), f"Expected runtime package root at {orket_root}"

    allowed_files = {
        "orket/interfaces/cli.py",
        "orket/cli/setup_wizard.py",
        "orket/discovery.py",
        # Verification subprocess contract writes JSON to stdout by design.
        "orket/domain/verification.py",
        # Standalone utility script with direct console output.
        "orket/orchestration/project_dumper_small.py",
        # Explicit command-line surfaces with direct user output.
        "orket/interfaces/orket_bundle_cli.py",
        "orket/interfaces/prompts_cli.py",
    }

    violations = []
    print_call = re.compile(r"(^|[^A-Za-z0-9_])print\s*\(")
    for py_file in orket_root.rglob("*.py"):
        rel = py_file.relative_to(repo_root).as_posix()
        text = py_file.read_text(encoding="utf-8")
        if not print_call.search(text):
            continue
        if rel in allowed_files:
            continue

        for lineno, line in enumerate(text.splitlines(), start=1):
            if print_call.search(line):
                violations.append(f"{rel}:{lineno}")

    assert not violations, "Disallowed print() usage found:\n" + "\n".join(violations)

