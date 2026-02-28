from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def digest_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def digest_tree(path: Path) -> str:
    file_paths = sorted(item for item in path.rglob("*") if item.is_file())
    material: list[bytes] = []
    for file_path in file_paths:
        rel = str(file_path.relative_to(path)).replace("\\", "/")
        material.append(rel.encode("utf-8"))
        material.append(b"\n")
        material.append(digest_file(file_path).encode("utf-8"))
        material.append(b"\n")
    return _sha256_bytes(b"".join(material))


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def deterministic_run_stamp(*, mode_id: str, model_id: str, seed: int, budget: int, baseline_digest: str) -> str:
    key = f"{mode_id}|{model_id}|{seed}|{budget}|{baseline_digest}"
    short = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    return f"{short}_reforge"


def prepare_run_dirs(run_root: Path) -> dict[str, Path]:
    if run_root.exists():
        shutil.rmtree(run_root)
    paths = {
        "root": run_root,
        "inputs": run_root / "inputs",
        "baseline_resolved": run_root / "inputs" / "baseline_pack_resolved",
        "mode": run_root / "inputs" / "mode.yaml",
        "candidates": run_root / "candidates",
        "eval": run_root / "eval",
        "diff": run_root / "diff",
        "summary": run_root / "summary.txt",
        "manifest": run_root / "manifest.json",
    }
    for key in ("root", "inputs", "baseline_resolved", "candidates", "eval", "diff"):
        paths[key].mkdir(parents=True, exist_ok=True)
    return paths


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    normalized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.write_text(normalized, encoding="utf-8")
