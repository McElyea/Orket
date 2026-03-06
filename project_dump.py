from __future__ import annotations

import argparse
import os
from pathlib import Path


def export_project_review_packet(
    root_dir: str = ".",
    output_file: str = "project_dump_review.txt",
    mode: str = "behavioral",
    max_file_size: int = 200_000,
    max_total_chars: int = 3_500_000,
    include_logs: bool = False,
    include_patch: bool = False,
) -> None:
    """
    Focused review dumper.

    Modes:
    - behavioral: prioritize runtime code + tests
    - architecture: prioritize docs/config/authority + selected surfaces
    """

    root = Path(root_dir).resolve()

    common_root_files = {
        "README.md",
        "AGENTS.md",
        "CURRENT_AUTHORITY.md",
        "pyproject.toml",
        "requirements.txt",
        "main.py",
        "server.py",
        "review-git-status.txt",
        "review-git-head.txt",
        "review-git-diffstat.txt",
    }

    if include_patch:
        common_root_files.add("review-working-tree.patch")

    if mode == "behavioral":
        include_top_dirs = {
            "orket",
            "tests",
            "scripts",
        }
    elif mode == "architecture":
        include_top_dirs = {
            "docs",
            "scripts",
            "orket",
        }
    else:
        raise ValueError("mode must be 'behavioral' or 'architecture'")

    include_ext = {
        ".py",
        ".md",
        ".toml",
        ".json",
        ".yml",
        ".yaml",
        ".ini",
        ".txt",
        ".patch",
    }

    hard_skip_dirs = {
        ".git",
        ".orket",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "dist",
        "build",
        "_review_stage",
        "_upload_packets",
        ".idea",
        ".vscode",
        "published",
    }

    hard_skip_file_names = {
        "project_dump_small.txt",
        "project_dump_review.txt",
        "project_dump_behavioral.txt",
        "project_dump_architecture.txt",
        "project_dump_behavioral_truth.txt",
        "orket-review-packet.zip",
        "package-lock.json",
        "poetry.lock",
        "uv.lock",
        "Pipfile.lock",
        ".DS_Store",
    }

    hard_skip_suffixes = {
        ".pyc",
        ".pyo",
        ".pyd",
        ".so",
        ".dll",
        ".exe",
        ".zip",
        ".tar",
        ".gz",
        ".7z",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".pdf",
        ".db",
        ".sqlite",
        ".sqlite3",
    }

    architecture_skip_paths = {
        "docs/internal/LMStudioData.txt",
    }

    logs: list[str] = []
    output_lines: list[str] = []
    total_chars = 0
    stop = False

    def log(msg: str) -> None:
        if include_logs:
            logs.append(msg)

    def is_hard_skipped_file(path: Path) -> bool:
        rel = path.relative_to(root).as_posix()
        if rel in architecture_skip_paths and mode == "architecture":
            return True
        if path.name in hard_skip_file_names:
            return True
        if path.suffix.lower() in hard_skip_suffixes:
            return True
        return False

    def should_include_root_file(path: Path) -> bool:
        return path.name in common_root_files

    def should_include_nested_file(path: Path) -> bool:
        rel = path.relative_to(root).as_posix()

        if path.suffix.lower() not in include_ext:
            return False

        if mode == "behavioral":
            if rel.startswith("docs/"):
                return False
            return True

        if mode == "architecture":
            if rel.startswith("docs/"):
                return True
            if rel.startswith("scripts/"):
                return True
            if rel.startswith("orket/runtime/"):
                return True
            if rel.startswith("orket/interfaces/"):
                return True
            return False

        return False

    def try_add_file(path: Path) -> bool:
        nonlocal total_chars

        rel = path.relative_to(root).as_posix()

        if is_hard_skipped_file(path):
            return False

        try:
            size = path.stat().st_size
        except OSError as e:
            log(f"[ERROR] {rel} (could not stat: {e})")
            return False

        if size > max_file_size:
            msg = f'<file path="{rel}">\n[Skipped: file too large ({size:,} bytes)]\n</file>'
            if total_chars + len(msg) > max_total_chars:
                log(f"[STOP] Total output cap reached before adding large-file marker for {rel}")
                return True
            output_lines.append(msg)
            total_chars += len(msg)
            log(f"[SKIP FILE] {rel} (too large: {size:,} bytes)")
            return False

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            content = f"[Could not read file: {e}]"
            log(f"[ERROR] {rel} (read error: {e})")

        entry = f'<file path="{rel}">\n{content}\n</file>'
        entry_len = len(entry)

        if total_chars + entry_len > max_total_chars:
            log(f"[STOP] Global output limit reached at {total_chars:,} chars before {rel}")
            return True

        output_lines.append(entry)
        total_chars += entry_len
        return False

    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if stop:
            break
        if child.is_file() and should_include_root_file(child):
            stop = try_add_file(child)

    for top_name in sorted(include_top_dirs):
        if stop:
            break

        top_path = root / top_name
        if not top_path.exists() or not top_path.is_dir():
            continue

        for dirpath, dirnames, filenames in os.walk(top_path):
            if stop:
                break

            dirpath_p = Path(dirpath)

            dirnames[:] = [
                d for d in sorted(dirnames)
                if d not in hard_skip_dirs
            ]

            for filename in sorted(filenames):
                if stop:
                    break

                path = dirpath_p / filename

                if is_hard_skipped_file(path):
                    continue
                if not should_include_nested_file(path):
                    continue

                stop = try_add_file(path)

    final_parts: list[str] = []
    if include_logs:
        final_parts.append("<log>\n" + "\n".join(logs) + "\n</log>")
    final_parts.extend(output_lines)

    final_output = "\n\n".join(final_parts)
    Path(output_file).write_text(final_output, encoding="utf-8", errors="replace")

    print(f"Export complete -> {output_file}")
    print(f"  Mode:          {mode}")
    print(f"  Files written: {len(output_lines)}")
    print(f"  Log entries:   {len(logs)}")
    print(f"  Output chars:  {len(final_output):,} (cap: {max_total_chars:,})")
    print(f"  include_patch: {include_patch}")
    print(f"  include_logs:  {include_logs}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a focused review packet.")
    parser.add_argument(
        "--arch",
        action="store_true",
        help="Export architecture/drift review packet instead of behavioral packet.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Override output file path.",
    )
    parser.add_argument(
        "--include-logs",
        action="store_true",
        help="Include compact log block in the output.",
    )
    parser.add_argument(
        "--include-patch",
        action="store_true",
        help="Include review-working-tree.patch in root file allowlist.",
    )
    parser.add_argument(
        "--max-file-size",
        type=int,
        default=160_000,
        help="Per-file size cap in bytes.",
    )
    parser.add_argument(
        "--max-total-chars",
        type=int,
        default=8_000_000,
        help="Global output size cap in characters.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    mode = "architecture" if args.arch else "behavioral"
    output_file = args.output or (
        "project_dump_architecture.txt" if args.arch else "project_dump_behavioral.txt"
    )

    print(f"Running focused review export ({mode})...")
    export_project_review_packet(
        ".",
        output_file=output_file,
        mode=mode,
        max_file_size=args.max_file_size,
        max_total_chars=args.max_total_chars,
        include_logs=args.include_logs,
        include_patch=args.include_patch,
    )