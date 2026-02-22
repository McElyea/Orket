#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


TRIPLET_SUFFIXES = {
    ".body.json": "body",
    ".links.json": "links",
    ".manifest.json": "manifest",
}


def _escape_message(message: str) -> str:
    return message.replace("\r", r"\r").replace("\n", r"\n")


def _pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _format_details(details: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in sorted(details):
        parts.append(f"{key}={_format_value(details[key])}")
    return " ".join(parts)


@dataclass
class Reporter:
    errors: int = 0
    warnings: int = 0
    lines: list[str] = field(default_factory=list)

    def emit(self, level: str, code: str, location: str, message: str, **details: Any) -> None:
        escaped_message = _escape_message(message)
        details_text = _format_details(details)
        line = f"[{level}] [STAGE:ci] [CODE:{code}] [LOC:{location}] {escaped_message}"
        if details_text:
            line = f"{line} | {details_text}"
        print(line)
        self.lines.append(line)
        if level == "FAIL":
            self.errors += 1

    def summary(self) -> int:
        outcome = "FAIL" if self.errors > 0 else "PASS"
        line = f"[SUMMARY] outcome={outcome} stage=ci errors={self.errors} warnings={self.warnings}"
        print(line)
        self.lines.append(line)
        return 1 if self.errors > 0 else 0


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _git_ref_exists(ref: str) -> bool:
    probe = _run_git(["rev-parse", "--verify", "--quiet", ref])
    return probe.returncode == 0


def _resolve_base_ref() -> str | None:
    # Explicit overrides first.
    direct_env = [os.getenv("BASE_REF"), os.getenv("CI_BASE_REF")]
    for ref in direct_env:
        if ref and _git_ref_exists(ref):
            return ref

    # Common PR base branch env names.
    branch_env = [
        os.getenv("GITHUB_BASE_REF"),
        os.getenv("GITEA_BASE_REF"),
    ]
    for branch in branch_env:
        if not branch:
            continue
        for candidate in (f"origin/{branch}", branch):
            if _git_ref_exists(candidate):
                return candidate

    # Push "before" SHA style env values.
    sha_env = [
        os.getenv("GITHUB_EVENT_BEFORE"),
        os.getenv("CI_COMMIT_BEFORE_SHA"),
    ]
    for sha in sha_env:
        if not sha:
            continue
        normalized = sha.strip()
        if not normalized or set(normalized) == {"0"}:
            continue
        if _git_ref_exists(normalized):
            return normalized

    return None


def _changed_files(base_ref: str) -> list[str]:
    # Three-dot gives merge-base style PR diff semantics.
    diff = _run_git(["diff", "--name-only", "--diff-filter=ACMR", f"{base_ref}...HEAD"])
    if diff.returncode != 0:
        raise RuntimeError(diff.stderr.strip() or "git diff failed")
    return [line.strip().replace("\\", "/") for line in diff.stdout.splitlines() if line.strip()]


def _triplet_roots() -> list[str]:
    roots_raw = os.getenv("TRIPLELOCK_ROOTS", "data/dto")
    roots = []
    for value in roots_raw.split(","):
        root = value.strip().replace("\\", "/").strip("/")
        if root:
            roots.append(root)
    return roots


def _is_under_roots(path: str, roots: list[str]) -> bool:
    return any(path == root or path.startswith(root + "/") for root in roots)


def _classify(changed: list[str], roots: list[str]) -> tuple[list[tuple[str, str, str]], list[str]]:
    triplet_candidates: list[tuple[str, str, str]] = []
    solo_json: list[str] = []
    for path in changed:
        if not path.endswith(".json"):
            continue
        matched = False
        if _is_under_roots(path, roots):
            for suffix, member in TRIPLET_SUFFIXES.items():
                if path.endswith(suffix):
                    stem = path[: -len(suffix)]
                    triplet_candidates.append((stem, member, path))
                    matched = True
                    break
        if not matched:
            solo_json.append(path)
    return triplet_candidates, solo_json


def _validate_triplets(
    candidates: list[tuple[str, str, str]],
    reporter: Reporter,
) -> None:
    stems: dict[str, dict[str, str]] = {}
    for stem, member, path in candidates:
        stems.setdefault(stem, {})[member] = path

    for stem in sorted(stems):
        mapping = stems[stem]
        required = ("body", "links", "manifest")
        missing = [name for name in required if name not in mapping]
        changed = [mapping[name] for name in required if name in mapping]
        loc = f"/ci/diff/{_pointer_token(stem)}"
        if missing:
            reporter.emit(
                "FAIL",
                "E_TRIPLET_INCOMPLETE",
                loc,
                "Triplet change is incomplete under data/dto.",
                changed=changed,
                missing=missing,
            )
        else:
            reporter.emit(
                "INFO",
                "I_TRIPLET_COMPLETE",
                loc,
                "Triplet complete.",
                changed=changed,
            )


def _validate_solo_json(paths: list[str], reporter: Reporter) -> None:
    for path in sorted(paths):
        loc = f"/ci/schema/{_pointer_token(path)}"
        try:
            text = Path(path).read_text(encoding="utf-8")
            json.loads(text)
        except Exception as exc:  # noqa: BLE001 - normalized to contract error code.
            reporter.emit(
                "FAIL",
                "E_BASE_SHAPE_INVALID_JSON",
                loc,
                "Invalid JSON parse.",
                path=path,
                error=str(exc),
            )
            continue
        reporter.emit(
            "INFO",
            "I_SOLO_JSON_VALID",
            loc,
            "Validated solo JSON parse.",
            path=path,
        )


def main() -> int:
    reporter = Reporter()
    roots = _triplet_roots()

    base_ref = _resolve_base_ref()
    if not base_ref:
        reporter.emit(
            "FAIL",
            "E_DIFF_UNAVAILABLE",
            "/ci/diff",
            "Unable to resolve base ref for git diff.",
            roots=roots,
        )
        return reporter.summary()

    try:
        changed = _changed_files(base_ref)
    except Exception as exc:  # noqa: BLE001 - normalized to contract error code.
        reporter.emit(
            "FAIL",
            "E_DIFF_UNAVAILABLE",
            "/ci/diff",
            "Unable to compute changed files.",
            base_ref=base_ref,
            error=str(exc),
        )
        return reporter.summary()

    reporter.emit(
        "INFO",
        "I_DIFF_READY",
        "/ci/diff",
        "Computed changed files.",
        base_ref=base_ref,
        changed_count=len(changed),
    )

    candidates, solo_json = _classify(changed, roots)

    if candidates:
        _validate_triplets(candidates, reporter)
    if solo_json:
        _validate_solo_json(solo_json, reporter)
    if not candidates and not solo_json:
        reporter.emit(
            "INFO",
            "I_NO_RELEVANT_JSON",
            "/ci/diff",
            "No relevant changed JSON files found.",
            changed_count=len(changed),
        )

    return reporter.summary()


if __name__ == "__main__":
    sys.exit(main())
