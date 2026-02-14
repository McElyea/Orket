from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _parse_semver(version: str) -> Tuple[int, int, int]:
    raw = str(version or "").strip()
    parts = raw.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid semantic version: {version!r}")
    try:
        major, minor, patch = (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError as exc:
        raise ValueError(f"Invalid semantic version: {version!r}") from exc
    return major, minor, patch


def _bump_semver(version: str, mode: str) -> str:
    major, minor, patch = _parse_semver(version)
    if mode == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if mode == "minor":
        return f"{major}.{minor + 1}.0"
    if mode == "major":
        return f"{major + 1}.0.0"
    raise ValueError(f"Unsupported bump mode: {mode}")


def _asset_dirs(root: Path, kind: str) -> List[Tuple[str, Path]]:
    if kind == "all":
        return [
            ("role", root / "model" / "core" / "roles"),
            ("dialect", root / "model" / "core" / "dialects"),
        ]
    if kind == "role":
        return [("role", root / "model" / "core" / "roles")]
    if kind == "dialect":
        return [("dialect", root / "model" / "core" / "dialects")]
    raise ValueError(f"Unsupported kind: {kind}")


def generate_candidates(
    *,
    root: Path,
    out_dir: Path,
    kind: str = "all",
    source_status: str = "stable",
    bump: str = "patch",
    note: str = "",
) -> Dict[str, Any]:
    created: List[Dict[str, Any]] = []
    generated_at = date.today().isoformat()
    advisory_note = note.strip() or "Offline optimize candidate generated."

    for asset_kind, directory in _asset_dirs(root, kind):
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            payload = _load_json(path)
            metadata = payload.get("prompt_metadata")
            if not isinstance(metadata, dict):
                continue

            status = str(metadata.get("status") or "").strip()
            if source_status and status != source_status:
                continue

            old_version = str(metadata.get("version") or "").strip()
            if not old_version:
                continue
            new_version = _bump_semver(old_version, bump)

            candidate_payload = json.loads(json.dumps(payload))
            candidate_metadata = dict(candidate_payload.get("prompt_metadata") or {})
            lineage = candidate_metadata.get("lineage")
            if not isinstance(lineage, dict):
                lineage = {"parent": old_version}
            lineage["parent"] = old_version
            candidate_metadata["lineage"] = lineage
            candidate_metadata["version"] = new_version
            candidate_metadata["status"] = "candidate"
            candidate_metadata["updated_at"] = generated_at
            changelog = candidate_metadata.get("changelog")
            if not isinstance(changelog, list):
                changelog = []
            changelog.append(
                {
                    "version": new_version,
                    "date": generated_at,
                    "notes": advisory_note,
                }
            )
            candidate_metadata["changelog"] = changelog
            candidate_payload["prompt_metadata"] = candidate_metadata

            target = out_dir / asset_kind / f"{path.stem}.{new_version}.candidate.json"
            _save_json(target, candidate_payload)
            created.append(
                {
                    "kind": asset_kind,
                    "source": str(path),
                    "target": str(target),
                    "id": candidate_metadata.get("id"),
                    "from_version": old_version,
                    "to_version": new_version,
                    "from_status": status,
                    "to_status": "candidate",
                }
            )

    manifest = {
        "generated_at": generated_at,
        "root": str(root),
        "output_dir": str(out_dir),
        "kind": kind,
        "source_status": source_status,
        "bump": bump,
        "note": advisory_note,
        "count": len(created),
        "candidates": created,
    }
    _save_json(out_dir / "manifest.json", manifest)
    return manifest


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate offline prompt candidate assets without mutating runtime assets."
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default="prompts/candidates")
    parser.add_argument("--kind", choices=["all", "role", "dialect"], default="all")
    parser.add_argument("--source-status", choices=["draft", "candidate", "canary", "stable", "deprecated"], default="stable")
    parser.add_argument("--bump", choices=["patch", "minor", "major"], default="patch")
    parser.add_argument("--note", default="")
    args = parser.parse_args(argv)

    manifest = generate_candidates(
        root=Path(args.root).resolve(),
        out_dir=Path(args.out).resolve(),
        kind=args.kind,
        source_status=args.source_status,
        bump=args.bump,
        note=args.note,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
