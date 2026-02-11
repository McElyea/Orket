from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


PY_FILE_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$")
NUMSTAT_RE = re.compile(r"^(\d+|-)\s+(\d+|-)\s+(.+)$")
SYMBOL_LINE_RE = re.compile(r"^[+-]\s*(?:async\s+def|def|class)\s+([A-Za-z_]\w*)")
HUNK_LINE_RE = re.compile(r"^[+-](?!\+\+|--)(.*)$")


@dataclass(frozen=True)
class Symbol:
    kind: str
    name: str
    file_path: str

    @property
    def key(self) -> str:
        return f"{self.file_path}:{self.kind}:{self.name}"


def _git(args: List[str]) -> str:
    result = subprocess.run(["git", *args], check=True, capture_output=True, text=False)
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return result.stdout.decode("utf-8", errors="replace")


def _iter_python_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if any(part in {".git", "__pycache__", ".venv", "venv", "env"} for part in path.parts):
            continue
        yield path


def _collect_symbols(repo_root: Path) -> Dict[str, List[Symbol]]:
    symbols_by_file: Dict[str, List[Symbol]] = defaultdict(list)
    for py_file in _iter_python_files(repo_root):
        rel = py_file.relative_to(repo_root).as_posix()
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except (SyntaxError, OSError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                symbols_by_file[rel].append(Symbol(kind="class", name=node.name, file_path=rel))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols_by_file[rel].append(Symbol(kind="function", name=node.name, file_path=rel))
    return symbols_by_file


def _file_level_churn(scope: str) -> Dict[str, Dict[str, int]]:
    output = _git(["log", "--numstat", "--format=tformat:", "--", scope])
    churn: Dict[str, Dict[str, int]] = defaultdict(lambda: {"adds": 0, "deletes": 0, "touches": 0})
    for line in output.splitlines():
        match = NUMSTAT_RE.match(line.strip())
        if not match:
            continue
        adds_raw, deletes_raw, path = match.groups()
        if path.endswith(".py") is False:
            continue
        adds = int(adds_raw) if adds_raw.isdigit() else 0
        deletes = int(deletes_raw) if deletes_raw.isdigit() else 0
        row = churn[path]
        row["adds"] += adds
        row["deletes"] += deletes
        row["touches"] += 1
    return dict(churn)


def _symbol_level_churn(
    scope: str,
    symbols_by_file: Dict[str, List[Symbol]],
) -> Dict[str, Dict[str, int]]:
    output = _git(["log", "-p", "--", scope])
    symbol_rows: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"touches": 0, "adds": 0, "deletes": 0, "inferred_hits": 0}
    )

    current_file: str | None = None
    changed_lines_by_file: Dict[str, List[str]] = defaultdict(list)

    for line in output.splitlines():
        file_match = PY_FILE_RE.match(line)
        if file_match:
            current_file = file_match.group(2)
            continue
        if current_file is None or not current_file.endswith(".py"):
            continue

        direct_symbol = SYMBOL_LINE_RE.match(line)
        if direct_symbol:
            name = direct_symbol.group(1)
            matched = [
                sym for sym in symbols_by_file.get(current_file, [])
                if sym.name == name
            ]
            for sym in matched:
                row = symbol_rows[sym.key]
                row["touches"] += 1
                row["adds"] += 1 if line.startswith("+") else 0
                row["deletes"] += 1 if line.startswith("-") else 0
            continue

        hunk_line = HUNK_LINE_RE.match(line)
        if hunk_line:
            changed_lines_by_file[current_file].append(hunk_line.group(1))

    for file_path, changed_lines in changed_lines_by_file.items():
        if not changed_lines or file_path not in symbols_by_file:
            continue
        body = "\n".join(changed_lines)
        for sym in symbols_by_file[file_path]:
            token = f"{sym.name}("
            if sym.kind == "class":
                token = sym.name
            hits = body.count(token)
            if hits > 0:
                symbol_rows[sym.key]["inferred_hits"] += hits

    return dict(symbol_rows)


def _top_rows(rows: Dict[str, Dict[str, int]], by: str, limit: int) -> List[Tuple[str, Dict[str, int]]]:
    return sorted(rows.items(), key=lambda kv: kv[1].get(by, 0), reverse=True)[:limit]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Orket code churn evidence.")
    parser.add_argument("--scope", default="orket", help="Path scope for churn analysis")
    parser.add_argument("--top", type=int, default=25, help="Top rows to include per section")
    parser.add_argument("--out", default="", help="Optional explicit output path")
    args = parser.parse_args()

    repo_root = Path(".").resolve()
    symbols_by_file = _collect_symbols(repo_root)
    file_rows = _file_level_churn(args.scope)
    symbol_rows = _symbol_level_churn(args.scope, symbols_by_file)

    top_files = _top_rows(file_rows, by="touches", limit=args.top)
    top_symbols = _top_rows(symbol_rows, by="touches", limit=args.top)
    top_symbols_inferred = _top_rows(symbol_rows, by="inferred_hits", limit=args.top)

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "scope": args.scope,
        "method": {
            "file_level": "git log --numstat touch/add/delete aggregation",
            "symbol_level": "git patch symbol-definition touches plus inferred body token hits",
            "notes": [
                "symbol-level churn is approximate",
                "renames/moves are attributed by current path in diffs",
            ],
        },
        "totals": {
            "files_analyzed": len(file_rows),
            "symbols_analyzed": len(symbol_rows),
        },
        "top_files_by_touches": [{"path": k, **v} for k, v in top_files],
        "top_symbols_by_touches": [{"symbol": k, **v} for k, v in top_symbols],
        "top_symbols_by_inferred_hits": [{"symbol": k, **v} for k, v in top_symbols_inferred],
    }

    out_path = Path(args.out) if args.out else Path(
        f"benchmarks/results/{datetime.now(UTC).strftime('%Y-%m-%d')}_churn.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote churn evidence: {out_path}")


if __name__ == "__main__":
    main()
