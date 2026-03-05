from __future__ import annotations

import ast
import csv
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
SCORES_CSV = REPO_ROOT / "scripts" / "tiering" / "script_tier_scores.csv"
OUTPUT_MD = REPO_ROOT / "scripts" / "tiering" / "SCRIPT_INDEX.md"
ARTIFACT_DIRS = (
    REPO_ROOT / "benchmarks" / "results",
    REPO_ROOT / "benchmarks" / "published",
)
ARTIFACT_EXTENSIONS = {".json", ".jsonl", ".md", ".txt", ".log", ".yaml", ".yml"}
MAX_ARTIFACT_BYTES = 1_000_000
MAX_LINKS_PER_SCRIPT = 3
TOKEN_STOPWORDS = {
    "run",
    "check",
    "build",
    "render",
    "report",
    "generate",
    "score",
    "compare",
    "update",
    "cleanup",
    "register",
    "execute",
    "list",
    "find",
    "manage",
    "play",
    "publish",
    "validate",
    "export",
    "decide",
    "analyze",
    "prototype",
    "sync",
    "audit",
    "docs",
    "workitem",
    "configure",
    "restore",
    "backup",
    "setup",
    "gen",
    "release",
}


@dataclass(frozen=True)
class ScriptScore:
    script: str
    final_path: str
    family: str
    final_score: int
    tier: str

    @property
    def domain(self) -> str:
        parts = self.final_path.split("/")
        if len(parts) >= 3 and parts[0] == "scripts":
            return parts[1]
        return "misc"


def _load_scores(path: Path) -> list[ScriptScore]:
    rows: list[ScriptScore] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                ScriptScore(
                    script=row["script"],
                    final_path=row["final_path"],
                    family=row["family"],
                    final_score=int(row["final_score"]),
                    tier=row["tier"],
                )
            )
    return rows


def _read_text(path: Path) -> str:
    if path.stat().st_size > MAX_ARTIFACT_BYTES:
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="latin-1")
        except OSError:
            return ""


def _extract_description(script_path: Path, script_name: str) -> str:
    if script_path.suffix != ".py" or not script_path.exists():
        return script_name.rsplit(".", 1)[0].replace("_", " ")

    text = _read_text(script_path)
    if not text:
        return script_name.rsplit(".", 1)[0].replace("_", " ")

    try:
        tree = ast.parse(text)
    except SyntaxError:
        tree = None

    if tree is not None:
        doc = ast.get_docstring(tree)
        if doc:
            first = doc.strip().splitlines()[0].strip()
            if first:
                return first

    parser_match = re.search(
        r"argparse\.ArgumentParser\((?:.|\n)*?description\s*=\s*([\"'])(.*?)\1",
        text,
        flags=re.DOTALL,
    )
    if parser_match:
        return " ".join(parser_match.group(2).strip().split())

    fn_match = re.search(r"def\s+main\([^)]*\)\s*->[^:]*:\n\s+\"\"\"(.*?)\"\"\"", text, flags=re.DOTALL)
    if fn_match:
        return " ".join(fn_match.group(1).strip().split())

    return script_name.rsplit(".", 1)[0].replace("_", " ")


def _iter_artifacts() -> Iterable[Path]:
    for root in ARTIFACT_DIRS:
        if not root.exists():
            continue
        for file in root.rglob("*"):
            if not file.is_file() or file.suffix.lower() not in ARTIFACT_EXTENSIONS:
                continue
            yield file


def _script_patterns(score: ScriptScore) -> tuple[str, ...]:
    stem = score.script.rsplit(".", 1)[0]
    old_rel = f"scripts/{score.tier}/{score.script}"
    new_rel = score.final_path
    dotted_old = f"scripts.{score.tier}.{stem}"
    dotted_new = new_rel.replace("/", ".").rsplit(".", 1)[0]
    return (new_rel, old_rel, dotted_new, dotted_old, score.script)


def _artifact_matches(patterns: tuple[str, ...], artifact_cache: dict[Path, str]) -> list[Path]:
    matches: list[Path] = []
    for path, text in artifact_cache.items():
        if not text:
            continue
        if any(token in text for token in patterns):
            matches.append(path)
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[:MAX_LINKS_PER_SCRIPT]


def _md_link(target: Path) -> str:
    rel = Path(str(target.relative_to(REPO_ROOT)).replace("\\", "/"))
    rel_from_output = Path(str(Path(rel).as_posix()))
    # Keep links repo-relative for Markdown viewers.
    return f"[`{rel_from_output.as_posix()}`](../../{rel_from_output.as_posix()})"


def _score_sort_key(row: ScriptScore) -> tuple[int, str]:
    return (-row.final_score, row.script)


def _semantic_artifact_matches(score: ScriptScore, artifacts: list[Path]) -> list[Path]:
    stem = score.script.rsplit(".", 1)[0].lower()
    tokens = [t for t in stem.split("_") if len(t) >= 3 and t not in TOKEN_STOPWORDS]
    if not tokens:
        return []

    scored: list[tuple[int, float, Path]] = []
    token_threshold = 2 if len(tokens) >= 2 else 1
    for path in artifacts:
        lowered = str(path.relative_to(REPO_ROOT)).replace("\\", "/").lower()
        overlap = sum(1 for t in tokens if t in lowered)
        if overlap < token_threshold:
            continue
        scored.append((overlap, path.stat().st_mtime, path))

    scored.sort(key=lambda item: (-item[0], -item[1]))
    return [item[2] for item in scored[:MAX_LINKS_PER_SCRIPT]]


def build_index() -> None:
    scores = _load_scores(SCORES_CSV)
    script_paths = {s.script: (REPO_ROOT / s.final_path) for s in scores}
    descriptions = {s.script: _extract_description(script_paths[s.script], s.script) for s in scores}

    artifacts = list(_iter_artifacts())
    artifact_cache = {path: _read_text(path) for path in artifacts}

    lines: list[str] = []
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    lines.append("# Script Index")
    lines.append("")
    lines.append(f"_Generated: {now}_")
    lines.append("")
    lines.append("This index maps script scores to purpose and recent artifact evidence.")
    lines.append("Scores come from `script_tier_scores.csv` (1-10 scale) and are grouped by functional family.")
    lines.append("")

    families = sorted({row.family for row in scores})
    for family in families:
        family_rows = sorted((r for r in scores if r.family == family), key=_score_sort_key)
        lines.append(f"## {family} ({len(family_rows)})")
        lines.append("")
        lines.append("| Script | Domain | Rating | Purpose | Recent Artifact Links |")
        lines.append("|---|---|---:|---|---|")
        for row in family_rows:
            script_path = f"`{row.final_path}`"
            domain = f"`{row.domain}`"
            rating = f"{row.final_score}/10"
            purpose = descriptions[row.script].replace("|", "\\|")
            direct_matches = _artifact_matches(_script_patterns(row), artifact_cache)
            semantic_matches = _semantic_artifact_matches(row, artifacts)
            merged: list[Path] = []
            for candidate in [*direct_matches, *semantic_matches]:
                if candidate not in merged:
                    merged.append(candidate)
                if len(merged) >= MAX_LINKS_PER_SCRIPT:
                    break
            if merged:
                rendered = "<br>".join(_md_link(path) for path in merged)
            else:
                rendered = "-"
            lines.append(f"| {script_path} | {domain} | {rating} | {purpose} | {rendered} |")
        lines.append("")

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build_index()
