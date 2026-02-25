from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List


ERROR_DOCS_LINK_MISSING = "E_DOCS_LINK_MISSING"
ERROR_DOCS_CANONICAL_MISSING = "E_DOCS_CANONICAL_MISSING"
ERROR_DOCS_HEADER_MISSING = "E_DOCS_HEADER_MISSING"
ERROR_DOCS_CROSSREF_MISSING = "E_DOCS_CROSSREF_MISSING"
ERROR_DOCS_USAGE = "E_DOCS_USAGE"

CHECK_DL1 = "DL1"
CHECK_DL2 = "DL2"
CHECK_DL3 = "DL3"
CHECK_DL4 = "DL4"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministic docs gate lint checks.")
    parser.add_argument("--root", default="docs", help="Docs root path.")
    parser.add_argument("--project", default="", help="Project slug under docs/projects (v1 supports core-pillars).")
    parser.add_argument("--strict", action="store_true", help="Enable strict active-doc coverage checks.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON report.")
    return parser.parse_args()


def _violation(*, code: str, check_id: str, path: str, message: str) -> Dict[str, str]:
    return {"code": code, "check_id": check_id, "path": path, "message": message}


def _strip_fenced_code(text: str) -> str:
    out: List[str] = []
    in_fence = False
    for line in text.splitlines():
        marker = line.strip()
        if marker.startswith("```") or marker.startswith("~~~"):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(line)
    return "\n".join(out)


_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
_ERROR_TOKEN_RE = re.compile(r"\bE_[A-Z0-9_]+\b")
_GATE_TOKEN_RE = re.compile(r"\b(?:A[1-9][0-9]*|D[1-9][0-9]*|API-[0-9]+)\b")

_DL4_DECLARATION_FILES = [
    "04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md",
    "05-BUCKET-D-FAILURE-LESSONS-REQUIREMENTS.md",
    "07-API-GENERATION-CONTRACT.md",
]


def _is_relative_target(raw_target: str) -> bool:
    text = str(raw_target or "").strip()
    if not text:
        return False
    lowered = text.lower()
    if lowered.startswith("#"):
        return False
    if lowered.startswith("http://") or lowered.startswith("https://") or lowered.startswith("mailto:"):
        return False
    return True


def _normalize_link_target(raw_target: str) -> str:
    text = str(raw_target or "").strip()
    if text.startswith("<") and text.endswith(">"):
        text = text[1:-1].strip()
    if " " in text and not text.startswith(("./", "../")):
        text = text.split(" ", 1)[0]
    if "#" in text:
        text = text.split("#", 1)[0]
    return text.strip()


def _iter_markdown_files(project_root: Path) -> List[Path]:
    return sorted(path for path in project_root.rglob("*.md") if path.is_file())


def _check_dl1_relative_links(project_root: Path, files: List[Path]) -> List[Dict[str, str]]:
    violations: List[Dict[str, str]] = []
    for path in files:
        text = _strip_fenced_code(path.read_text(encoding="utf-8"))
        for raw_target in _LINK_RE.findall(text):
            if not _is_relative_target(raw_target):
                continue
            normalized = _normalize_link_target(raw_target)
            if not normalized:
                continue
            candidate = (path.parent / normalized).resolve()
            if candidate.exists():
                continue
            violations.append(
                _violation(
                    code=ERROR_DOCS_LINK_MISSING,
                    check_id=CHECK_DL1,
                    path=str(path).replace("\\", "/"),
                    message=f"missing relative link target '{normalized}'",
                )
            )
    return violations


def _canonical_paths_from_readme(readme_path: Path) -> List[str]:
    if not readme_path.exists():
        return []
    lines = readme_path.read_text(encoding="utf-8").splitlines()
    in_canonical = False
    rows: List[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.lower() == "## canonical docs":
            in_canonical = True
            continue
        if in_canonical and stripped.startswith("## "):
            break
        if not in_canonical:
            continue
        for raw in re.findall(r"`([^`]+)`", line):
            item = str(raw).strip()
            if item.startswith("docs/projects/"):
                rows.append(item)
    return sorted(set(rows))


def _check_dl2_canonical_presence(docs_root: Path, project_root: Path) -> List[Dict[str, str]]:
    violations: List[Dict[str, str]] = []
    readme = project_root / "README.md"
    canonical = _canonical_paths_from_readme(readme)
    if not canonical:
        violations.append(
            _violation(
                code=ERROR_DOCS_CANONICAL_MISSING,
                check_id=CHECK_DL2,
                path=str(readme).replace("\\", "/"),
                message="canonical doc registry not found or empty",
            )
        )
        return violations

    repo_root = docs_root.resolve().parent
    for canonical_path in canonical:
        candidate = (repo_root / canonical_path).resolve()
        if candidate.exists():
            continue
        violations.append(
            _violation(
                code=ERROR_DOCS_CANONICAL_MISSING,
                check_id=CHECK_DL2,
                path=canonical_path.replace("\\", "/"),
                message="canonical doc listed in registry is missing",
            )
        )
    return violations


def _is_active_doc(lines: List[str]) -> bool:
    for line in lines[:40]:
        if "status: active" in line.strip().lower():
            return True
    return False


def _check_dl3_active_headers(files: List[Path]) -> List[Dict[str, str]]:
    violations: List[Dict[str, str]] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        if not _is_active_doc(lines):
            continue

        probe = lines[:40]
        missing_fields: List[str] = []
        if not any(line.strip().lower().startswith("date:") for line in probe):
            missing_fields.append("Date")
        if not any(line.strip().lower().startswith("status:") for line in probe):
            missing_fields.append("Status")
        if not any(line.strip().lower() == "## objective" for line in lines[:120]):
            missing_fields.append("ObjectiveHeading")

        for field_name in missing_fields:
            violations.append(
                _violation(
                    code=ERROR_DOCS_HEADER_MISSING,
                    check_id=CHECK_DL3,
                    path=str(path).replace("\\", "/"),
                    message=f"active doc missing required field '{field_name}'",
                )
            )
    return violations


def _check_strict_registry_coverage(files: List[Path], canonical_paths: List[str]) -> List[Dict[str, str]]:
    canonical_set = {item.replace("\\", "/") for item in canonical_paths}
    violations: List[Dict[str, str]] = []
    for path in files:
        text_lines = path.read_text(encoding="utf-8").splitlines()
        if not _is_active_doc(text_lines):
            continue
        rel = str(path).replace("\\", "/")
        if rel in canonical_set:
            continue
        marker = "/docs/projects/"
        if marker in rel:
            suffix = rel.split(marker, 1)[1]
            if f"docs/projects/{suffix}" in canonical_set:
                continue
        violations.append(
            _violation(
                code=ERROR_DOCS_CANONICAL_MISSING,
                check_id=CHECK_DL2,
                path=rel,
                message="active doc must appear in canonical registry in strict mode",
            )
        )
    return violations


def _extract_tokens(text: str, pattern: re.Pattern[str]) -> List[str]:
    return sorted(set(pattern.findall(text)))


def _declared_crossref_tokens(project_root: Path) -> Dict[str, set[str]]:
    declared_error_tokens: set[str] = set()
    declared_gate_tokens: set[str] = set()
    for name in _DL4_DECLARATION_FILES:
        path = project_root / name
        if not path.exists():
            continue
        text = _strip_fenced_code(path.read_text(encoding="utf-8"))
        declared_error_tokens.update(_extract_tokens(text, _ERROR_TOKEN_RE))
        declared_gate_tokens.update(_extract_tokens(text, _GATE_TOKEN_RE))
    return {
        "error_tokens": declared_error_tokens,
        "gate_tokens": declared_gate_tokens,
    }


def _check_dl4_crossrefs(project_root: Path, files: List[Path]) -> List[Dict[str, str]]:
    violations: List[Dict[str, str]] = []
    declared = _declared_crossref_tokens(project_root)
    declared_errors = declared["error_tokens"]
    declared_gates = declared["gate_tokens"]

    for path in files:
        text = _strip_fenced_code(path.read_text(encoding="utf-8"))
        for token in _extract_tokens(text, _ERROR_TOKEN_RE):
            if token in declared_errors:
                continue
            violations.append(
                _violation(
                    code=ERROR_DOCS_CROSSREF_MISSING,
                    check_id=CHECK_DL4,
                    path=str(path).replace("\\", "/"),
                    message=f"error token '{token}' is not declared in canonical contract files",
                )
            )
        for token in _extract_tokens(text, _GATE_TOKEN_RE):
            if token in declared_gates:
                continue
            violations.append(
                _violation(
                    code=ERROR_DOCS_CROSSREF_MISSING,
                    check_id=CHECK_DL4,
                    path=str(path).replace("\\", "/"),
                    message=f"acceptance token '{token}' is not declared in canonical contract files",
                )
            )
    return violations


def _human_report(payload: Dict[str, Any]) -> str:
    lines: List[str] = []
    for row in payload.get("violations", []):
        lines.append(f"[{row['check_id']}] {row['code']} {row['path']}: {row['message']}")
    if payload["status"] == "PASS":
        lines.append(f"PASS: checked {payload['checked_files']} files; 0 violations.")
    else:
        lines.append(f"FAIL: checked {payload['checked_files']} files; {payload['violation_count']} violations.")
    return "\n".join(lines)


def main() -> int:
    args = _parse_args()
    project = str(args.project or "").strip()
    if project != "core-pillars":
        payload = {
            "status": "FAIL",
            "project": project,
            "checked_files": 0,
            "violation_count": 1,
            "violations": [
                _violation(
                    code=ERROR_DOCS_USAGE,
                    check_id="USAGE",
                    path="scripts/docs_lint.py",
                    message="--project core-pillars is required in v1",
                )
            ],
        }
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(_human_report(payload))
        return 2

    docs_root = Path(str(args.root)).resolve()
    project_root = docs_root / "projects" / project
    files = _iter_markdown_files(project_root)

    violations: List[Dict[str, str]] = []
    violations.extend(_check_dl1_relative_links(project_root, files))
    violations.extend(_check_dl2_canonical_presence(docs_root, project_root))
    violations.extend(_check_dl3_active_headers(files))

    if bool(args.strict):
        canonical = _canonical_paths_from_readme(project_root / "README.md")
        violations.extend(_check_strict_registry_coverage(files, canonical))
        violations.extend(_check_dl4_crossrefs(project_root, files))

    violations = sorted(violations, key=lambda row: (row["path"], row["check_id"], row["message"], row["code"]))
    payload = {
        "status": "PASS" if not violations else "FAIL",
        "project": project,
        "checked_files": len(files),
        "violation_count": len(violations),
        "violations": violations,
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(_human_report(payload))
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
