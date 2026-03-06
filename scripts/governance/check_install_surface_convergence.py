from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger


DEFAULT_CANONICAL_COMMAND = 'python -m pip install -e ".[dev]"'
DEFAULT_LEGACY_COMMAND = "pip install -r requirements.txt"
DEFAULT_DOC_PATHS = ("README.md", "docs/CONTRIBUTOR.md", "docs/RUNBOOK.md")
DEFAULT_WORKFLOW_GLOB = ".gitea/workflows/*.yml"
DEFAULT_REQUIREMENTS_PATH = "requirements.txt"
QUALITY_WORKFLOW_PATH = ".gitea/workflows/quality.yml"
REQUIRED_CI_GATE_INVOCATION = "python scripts/governance/check_install_surface_convergence.py"
ALLOWED_REQUIREMENTS_LINE_TOKENS = ("-e .[dev]", '-e ".[dev]"')


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check install-surface convergence for docs, workflows, and derived requirements shim.",
    )
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--canonical-command", default=DEFAULT_CANONICAL_COMMAND, help="Expected install command.")
    parser.add_argument("--legacy-command", default=DEFAULT_LEGACY_COMMAND, help="Legacy command that must not appear.")
    parser.add_argument(
        "--docs-path",
        action="append",
        default=[],
        help="Doc path relative to repo root. Repeatable; default checks README/RUNBOOK/CONTRIBUTOR.",
    )
    parser.add_argument("--workflow-glob", default=DEFAULT_WORKFLOW_GLOB, help="Workflow glob relative to repo root.")
    parser.add_argument(
        "--requirements-path",
        default=DEFAULT_REQUIREMENTS_PATH,
        help="Requirements shim path relative to repo root.",
    )
    parser.add_argument("--out", default="", help="Optional JSON output path for machine-readable check results.")
    return parser


def _read_text(path: Path, failures: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        failures.append(f"unable to read {path.as_posix()}: {exc}")
        return ""


def _collect_doc_assertions(
    *,
    repo_root: Path,
    doc_paths: list[str],
    canonical_command: str,
    legacy_command: str,
    failures: list[str],
) -> list[dict[str, Any]]:
    assertions: list[dict[str, Any]] = []
    for raw in doc_paths:
        doc_path = repo_root / raw
        if not doc_path.exists():
            failures.append(f"missing docs file: {doc_path.as_posix()}")
            continue
        text = _read_text(doc_path, failures)
        has_canonical = canonical_command in text
        has_legacy = legacy_command in text
        assertions.append(
            {
                "id": f"doc_{raw.replace('/', '_').replace('.', '_')}_canonical_install_command",
                "passed": has_canonical and not has_legacy,
                "detail": (
                    f"path={doc_path.as_posix()} canonical_present={has_canonical} "
                    f"legacy_present={has_legacy}"
                ),
            }
        )
        if not has_canonical:
            failures.append(f"canonical install command missing from {doc_path.as_posix()}")
        if has_legacy:
            failures.append(f"legacy install command found in {doc_path.as_posix()}")
    return assertions


def _workflow_needs_install_check(text: str) -> bool:
    return "pip install" in text


def _collect_workflow_assertions(
    *,
    repo_root: Path,
    workflow_glob: str,
    canonical_command: str,
    legacy_command: str,
    failures: list[str],
) -> list[dict[str, Any]]:
    workflow_paths = sorted((repo_root / ".").glob(workflow_glob))
    if not workflow_paths:
        failures.append(f"workflow glob returned no files: {(repo_root / workflow_glob).as_posix()}")
        return []

    assertions: list[dict[str, Any]] = []
    for workflow_path in workflow_paths:
        text = _read_text(workflow_path, failures)
        has_legacy = legacy_command in text
        needs_check = _workflow_needs_install_check(text)
        has_canonical = canonical_command in text
        passed = (not has_legacy) and (not needs_check or has_canonical)
        assertions.append(
            {
                "id": f"workflow_{workflow_path.name.replace('.', '_')}_install_surface",
                "passed": passed,
                "detail": (
                    f"path={workflow_path.as_posix()} needs_check={needs_check} "
                    f"canonical_present={has_canonical} legacy_present={has_legacy}"
                ),
            }
        )
        if has_legacy:
            failures.append(f"legacy install command found in workflow: {workflow_path.as_posix()}")
        if needs_check and not has_canonical:
            failures.append(f"workflow missing canonical install command: {workflow_path.as_posix()}")
    return assertions


def _clean_requirements_lines(text: str) -> list[str]:
    cleaned: list[str] = []
    for line in text.splitlines():
        token = line.strip()
        if not token or token.startswith("#"):
            continue
        cleaned.append(token)
    return cleaned


def _collect_requirements_assertion(
    *,
    repo_root: Path,
    requirements_path: str,
    failures: list[str],
) -> dict[str, Any]:
    path = repo_root / requirements_path
    if not path.exists():
        failures.append(f"missing requirements shim: {path.as_posix()}")
        return {
            "id": "requirements_shim_derives_from_pyproject",
            "passed": False,
            "detail": f"path={path.as_posix()} missing",
        }

    text = _read_text(path, failures)
    lines = _clean_requirements_lines(text)
    valid = len(lines) == 1 and lines[0] in ALLOWED_REQUIREMENTS_LINE_TOKENS
    if not valid:
        failures.append(
            "requirements shim drifted; expected exactly one editable pyproject line "
            f"({ALLOWED_REQUIREMENTS_LINE_TOKENS}) and found {lines}"
        )
    return {
        "id": "requirements_shim_derives_from_pyproject",
        "passed": valid,
        "detail": f"path={path.as_posix()} active_lines={lines}",
    }


def _collect_ci_gate_assertion(*, repo_root: Path, failures: list[str]) -> dict[str, Any]:
    path = repo_root / QUALITY_WORKFLOW_PATH
    if not path.exists():
        failures.append(f"missing quality workflow: {path.as_posix()}")
        return {
            "id": "ci_gate_enforces_install_surface_convergence",
            "passed": False,
            "detail": f"path={path.as_posix()} missing",
        }

    text = _read_text(path, failures)
    present = REQUIRED_CI_GATE_INVOCATION in text
    if not present:
        failures.append(
            "quality workflow missing install surface gate invocation: "
            f"{REQUIRED_CI_GATE_INVOCATION}"
        )
    return {
        "id": "ci_gate_enforces_install_surface_convergence",
        "passed": present,
        "detail": f"path={path.as_posix()} gate_invocation_present={present}",
    }


def _build_result_payload(
    *,
    repo_root: Path,
    canonical_command: str,
    legacy_command: str,
    assertions: list[dict[str, Any]],
    failures: list[str],
) -> dict[str, Any]:
    all_passed = bool(assertions) and all(bool(row.get("passed")) for row in assertions) and not failures
    return {
        "schema_version": "governance.install_surface_convergence.v1",
        "repo_root": repo_root.resolve().as_posix(),
        "status": "PASS" if all_passed else "FAIL",
        "canonical_command": canonical_command,
        "legacy_command": legacy_command,
        "assertions": assertions,
        "failures": failures,
        "environment": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "python_executable": sys.executable,
        },
    }


def _resolve_doc_paths(raw_paths: list[str]) -> list[str]:
    if raw_paths:
        return [str(token).replace("\\", "/").strip() for token in raw_paths if str(token).strip()]
    return list(DEFAULT_DOC_PATHS)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = Path(str(args.repo_root)).resolve()
    canonical_command = str(args.canonical_command).strip()
    legacy_command = str(args.legacy_command).strip()
    doc_paths = _resolve_doc_paths(list(args.docs_path or []))

    failures: list[str] = []
    assertions: list[dict[str, Any]] = []
    assertions.extend(
        _collect_doc_assertions(
            repo_root=repo_root,
            doc_paths=doc_paths,
            canonical_command=canonical_command,
            legacy_command=legacy_command,
            failures=failures,
        )
    )
    assertions.extend(
        _collect_workflow_assertions(
            repo_root=repo_root,
            workflow_glob=str(args.workflow_glob),
            canonical_command=canonical_command,
            legacy_command=legacy_command,
            failures=failures,
        )
    )
    assertions.append(
        _collect_requirements_assertion(
            repo_root=repo_root,
            requirements_path=str(args.requirements_path),
            failures=failures,
        )
    )
    assertions.append(_collect_ci_gate_assertion(repo_root=repo_root, failures=failures))

    result = _build_result_payload(
        repo_root=repo_root,
        canonical_command=canonical_command,
        legacy_command=legacy_command,
        assertions=assertions,
        failures=failures,
    )
    out_path = str(args.out).strip()
    if out_path:
        write_payload_with_diff_ledger(Path(out_path), result)

    if result["status"] == "PASS":
        print("Install surface convergence check passed.")
        return 0

    print("Install surface convergence check failed:")
    for failure in failures:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
