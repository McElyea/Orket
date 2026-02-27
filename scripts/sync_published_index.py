from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_index(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise SystemExit(f"E_INDEX_MISSING {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"E_INDEX_JSON_INVALID {path}: {exc}") from exc


def _require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise SystemExit(f"{code} {detail}")


def _validate_index(index: dict[str, Any], index_path: Path) -> None:
    _require(isinstance(index, dict), "E_INDEX_SHAPE", "index must be object")
    _require(isinstance(index.get("catalog_v"), str), "E_INDEX_FIELD", "catalog_v required")
    _require(isinstance(index.get("updated_on"), str), "E_INDEX_FIELD", "updated_on required")
    _require(isinstance(index.get("root"), str), "E_INDEX_FIELD", "root required")
    _require(isinstance(index.get("highlight_id"), str), "E_INDEX_FIELD", "highlight_id required")
    _require(isinstance(index.get("artifacts"), list), "E_INDEX_FIELD", "artifacts[] required")

    root = (index_path.parent / index["root"]).resolve() if not Path(index["root"]).is_absolute() else Path(index["root"])
    if not root.exists():
        # fallback for repo-relative root
        root = (Path.cwd() / index["root"]).resolve()
    _require(root.exists(), "E_ROOT_MISSING", f"{index['root']}")

    ids: set[str] = set()
    rel_paths: set[str] = set()
    categories: set[str] = set()

    for row in index["artifacts"]:
        _require(isinstance(row, dict), "E_ARTIFACT_SHAPE", "artifact row must be object")
        for key in ("id", "category", "path", "title", "summary", "signals", "source_path", "publish_reviewed"):
            _require(key in row, "E_ARTIFACT_FIELD", f"{key} missing")
        _require(isinstance(row["id"], str) and row["id"], "E_ARTIFACT_ID", "id must be non-empty string")
        _require(row["id"] not in ids, "E_ARTIFACT_DUP_ID", row["id"])
        ids.add(row["id"])

        _require(isinstance(row["category"], str) and row["category"], "E_ARTIFACT_CATEGORY", row["id"])
        categories.add(row["category"])

        _require(isinstance(row["path"], str) and row["path"], "E_ARTIFACT_PATH", row["id"])
        _require(row["path"] not in rel_paths, "E_ARTIFACT_DUP_PATH", row["path"])
        rel_paths.add(row["path"])
        _require(row["path"].startswith(f"{row['category']}/"), "E_ARTIFACT_PATH_CATEGORY", row["path"])
        target = root / row["path"]
        _require(target.exists(), "E_ARTIFACT_FILE_MISSING", str(target))

        _require(isinstance(row["title"], str) and row["title"], "E_ARTIFACT_TITLE", row["id"])
        _require(isinstance(row["summary"], str) and row["summary"], "E_ARTIFACT_SUMMARY", row["id"])
        _require(isinstance(row["signals"], list), "E_ARTIFACT_SIGNALS", row["id"])
        _require(all(isinstance(item, str) and item for item in row["signals"]), "E_ARTIFACT_SIGNALS", row["id"])
        _require(isinstance(row["source_path"], str) and row["source_path"], "E_ARTIFACT_SOURCE", row["id"])
        _require(isinstance(row["publish_reviewed"], bool), "E_ARTIFACT_REVIEWED", row["id"])

    _require(index["highlight_id"] in ids, "E_HIGHLIGHT_ID", index["highlight_id"])

    if "reading_paths" in index:
        _require(isinstance(index["reading_paths"], list), "E_READING_PATHS", "reading_paths must be array")
        for row in index["reading_paths"]:
            _require(isinstance(row, dict), "E_READING_PATHS", "row must be object")
            _require(isinstance(row.get("name"), str) and row["name"], "E_READING_PATH_NAME", "name required")
            _require(isinstance(row.get("artifact_ids"), list), "E_READING_PATH_IDS", row.get("name", ""))
            for artifact_id in row["artifact_ids"]:
                _require(artifact_id in ids, "E_READING_PATH_UNKNOWN_ID", str(artifact_id))


def _render_readme(index: dict[str, Any]) -> str:
    artifacts = list(index["artifacts"])
    categories = sorted({row["category"] for row in artifacts})
    by_id = {row["id"]: row for row in artifacts}
    highlight = by_id[index["highlight_id"]]

    lines: list[str] = []
    lines.append("# Published Benchmark Index")
    lines.append("")
    lines.append(f"Last updated: {index['updated_on']}")
    lines.append("")
    lines.append("This directory is the curated, share-safe benchmark lane.")
    lines.append("")
    lines.append("## Folder Layout")
    for idx, category in enumerate(categories, start=1):
        lines.append(f"{idx}. `{category}/`")
    lines.append(f"{len(categories) + 1}. `index.json`")
    lines.append("   - Machine-readable catalog for automation and dashboards.")
    lines.append("")
    lines.append("## Latest Highlight")
    lines.append(f"1. `{highlight['path']}` (`{highlight['id']}`)")
    lines.append(f"   - {highlight['summary']}")
    lines.append("")
    lines.append("## Artifact Directory")
    lines.append("")
    lines.append("| ID | Category | File | Title | What it proves | Key signals |")
    lines.append("|---|---|---|---|---|---|")
    for row in artifacts:
        signals = ", ".join(f"`{item}`" for item in row["signals"])
        lines.append(
            f"| {row['id']} | {row['category']} | `{row['path']}` | {row['title']} | {row['summary']} | {signals} |"
        )

    reading_paths = index.get("reading_paths", [])
    if reading_paths:
        lines.append("")
        lines.append("## Reading Paths")
        for idx, row in enumerate(reading_paths, start=1):
            ids = " -> ".join(f"`{item}`" for item in row["artifact_ids"])
            lines.append(f"{idx}. {row['name']}: {ids}")

    lines.append("")
    lines.append("## Publish Workflow")
    lines.append("1. Copy curated artifact(s) into the correct category folder.")
    lines.append("2. Add/update artifact rows in `index.json`.")
    lines.append("3. Regenerate this README:")
    lines.append("```bash")
    lines.append("python scripts/sync_published_index.py --write")
    lines.append("```")
    lines.append("4. Validate before commit:")
    lines.append("```bash")
    lines.append("python scripts/sync_published_index.py --check")
    lines.append("```")
    lines.append("5. Do not overwrite prior published artifacts; add versioned files instead.")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and render benchmarks/published README from index.json")
    parser.add_argument("--index", default="benchmarks/published/index.json")
    parser.add_argument("--readme", default="benchmarks/published/README.md")
    parser.add_argument("--write", action="store_true", help="Write generated README.")
    parser.add_argument("--check", action="store_true", help="Validate index and README sync.")
    args = parser.parse_args()

    index_path = Path(args.index)
    readme_path = Path(args.readme)
    index = _load_index(index_path)
    _validate_index(index, index_path=index_path)
    rendered = _render_readme(index)

    if args.write:
        readme_path.parent.mkdir(parents=True, exist_ok=True)
        readme_path.write_text(rendered, encoding="utf-8")
        print(f"WROTE {readme_path}")

    if args.check:
        existing = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
        if existing != rendered:
            raise SystemExit("E_README_OUT_OF_SYNC run: python scripts/sync_published_index.py --write")
        print("PASS published index/readme sync")

    if not args.write and not args.check:
        print("PASS index validated")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
