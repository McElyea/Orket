from __future__ import annotations

import re
import sys
from pathlib import Path


ROADMAP_PATH = Path("docs/ROADMAP.md")
PROJECTS_ROOT = Path("docs/projects")
NON_ARCHIVE_COMPLETED_ALLOWLIST = {"core-pillars"}


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


def main() -> int:
    if not ROADMAP_PATH.exists():
        print(f"ERROR: missing roadmap file: {ROADMAP_PATH}")
        return 1
    if not PROJECTS_ROOT.exists():
        print(f"ERROR: missing project root: {PROJECTS_ROOT}")
        return 1

    roadmap_text = ROADMAP_PATH.read_text(encoding="utf-8")
    rows = _project_rows(roadmap_text)
    index_by_project = {row["project"]: row for row in rows}

    failures: list[str] = []

    non_archive_dirs = sorted(
        [
            p.name
            for p in PROJECTS_ROOT.iterdir()
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

        if status == "completed":
            if path.startswith("docs/projects/") and "/archive/" not in path.replace("\\", "/"):
                if project not in NON_ARCHIVE_COMPLETED_ALLOWLIST:
                    failures.append(
                        "Completed project should be archived or explicitly allowlisted: "
                        f"{project} -> {path}"
                    )
        if not path.startswith("docs/projects/") and not path.startswith("docs/specs/"):
            continue
        if "/archive/" in path.replace("\\", "/"):
            continue
        if not Path(path).exists():
            failures.append(f"Roadmap path does not exist: {project} -> {path}")

    if failures:
        print("Docs project hygiene check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Docs project hygiene check passed.")
    print(f"Non-archive project folders: {', '.join(non_archive_dirs) if non_archive_dirs else '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
