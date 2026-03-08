from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROADMAP_RELATIVE_PATH = Path("docs/ROADMAP.md")
PROJECTS_RELATIVE_ROOT = Path("docs/projects")
TECHDEBT_RELATIVE_ROOT = PROJECTS_RELATIVE_ROOT / "techdebt"
TECHDEBT_MAINTENANCE_FILES = {
    "README.md",
    "Recurring-Maintenance-Checklist.md",
}
TECHDEBT_ACTIVE_CYCLE_PATTERN = re.compile(r"techdebt active cycle `(?P<cycle>[A-Z]+[0-9]{8})`")
TECHDEBT_CYCLE_FILE_PATTERN = re.compile(r"^(?P<cycle>[A-Z]+[0-9]{8})(?:[-_].*)?$")
STATUS_PATTERN = re.compile(r"^Status:\s*(?P<status>.+)$", re.MULTILINE)


def _project_rows(roadmap_text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    pattern = re.compile(
        r"^\|\s*(?P<project>[^|]+?)\s*\|\s*(?P<status>[^|]+?)\s*\|\s*(?P<priority>[^|]+?)\s*\|\s*`(?P<path>[^`]+)`\s*\|",
        re.MULTILINE,
    )
    for match in pattern.finditer(roadmap_text):
        rows.append(
            {
                "project": match.group("project").strip(),
                "status": match.group("status").strip().lower(),
                "priority": match.group("priority").strip(),
                "path": match.group("path").strip(),
            }
        )
    return rows


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check docs/projects roadmap and techdebt hygiene.")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing docs/ROADMAP.md and docs/projects/.",
    )
    return parser.parse_args(argv)


def _status_value(path: Path) -> str | None:
    match = STATUS_PATTERN.search(path.read_text(encoding="utf-8"))
    if match is None:
        return None
    return match.group("status").strip()


def _active_techdebt_cycle_ids(roadmap_text: str) -> set[str]:
    return {match.group("cycle") for match in TECHDEBT_ACTIVE_CYCLE_PATTERN.finditer(roadmap_text)}


def _techdebt_file_failures(techdebt_root: Path, active_cycle_ids: set[str]) -> list[str]:
    failures: list[str] = []
    if not techdebt_root.exists():
        return failures

    for path in sorted(p for p in techdebt_root.iterdir() if p.is_file()):
        if path.name in TECHDEBT_MAINTENANCE_FILES:
            continue

        status = _status_value(path)
        cycle_match = TECHDEBT_CYCLE_FILE_PATTERN.match(path.name)
        cycle_id = cycle_match.group("cycle") if cycle_match is not None else None
        normalized_status = status.lower() if status is not None else ""

        if cycle_id is not None and cycle_id not in active_cycle_ids:
            suffix = f" (status: {status})" if status is not None else ""
            failures.append(
                "Non-active techdebt cycle doc should be archived: "
                f"{path.as_posix()} (cycle {cycle_id} not listed active in docs/ROADMAP.md){suffix}"
            )
            continue

        if normalized_status.startswith("completed") or normalized_status.startswith("archived"):
            failures.append(
                "Completed/archived techdebt doc must not remain in active techdebt scope: "
                f"{path.as_posix()} (status: {status})"
            )

    return failures


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    roadmap_path = repo_root / ROADMAP_RELATIVE_PATH
    projects_root = repo_root / PROJECTS_RELATIVE_ROOT
    techdebt_root = repo_root / TECHDEBT_RELATIVE_ROOT

    if not roadmap_path.exists():
        print(f"ERROR: missing roadmap file: {roadmap_path}")
        return 1
    if not projects_root.exists():
        print(f"ERROR: missing project root: {projects_root}")
        return 1

    roadmap_text = roadmap_path.read_text(encoding="utf-8")
    rows = _project_rows(roadmap_text)
    index_by_project = {row["project"]: row for row in rows}

    failures: list[str] = []

    non_archive_dirs = sorted(
        [
            p.name
            for p in projects_root.iterdir()
            if p.is_dir() and p.name.lower() != "archive"
        ]
    )

    for project in non_archive_dirs:
        if project not in index_by_project:
            failures.append(
                f"Project folder missing from roadmap Project Index: docs/projects/{project}/"
            )

    active_rows = [r for r in rows if r["project"].lower() != "archive"]
    for row in active_rows:
        project = row["project"]
        status = row["status"]
        path = row["path"]

        if status.startswith("completed"):
            if path.startswith("docs/projects/") and "/archive/" not in path.replace("\\", "/"):
                failures.append(f"Completed project should be archived: {project} -> {path}")
        if not path.startswith("docs/projects/") and not path.startswith("docs/specs/"):
            continue
        if "/archive/" in path.replace("\\", "/"):
            continue
        if not (repo_root / path).exists():
            failures.append(f"Roadmap path does not exist: {project} -> {path}")

    failures.extend(_techdebt_file_failures(techdebt_root, _active_techdebt_cycle_ids(roadmap_text)))

    if failures:
        print("Docs project hygiene check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Docs project hygiene check passed.")
    print(f"Non-archive project folders: {', '.join(non_archive_dirs) if non_archive_dirs else '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
