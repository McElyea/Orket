from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.reforger.packs import PackValidationError, resolve_pack, resolved_pack_digest


def _seed_pack(
    pack_dir: Path,
    *,
    pack_id: str,
    version: str = "1.0.0",
    extends: str | None = None,
    system_text: str = "system",
    constraints_text: str = "rules: []\n",
) -> None:
    pack_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {"id": pack_id, "version": version}
    if extends:
        payload["extends"] = extends
    (pack_dir / "pack.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (pack_dir / "system.txt").write_text(system_text, encoding="utf-8")
    (pack_dir / "constraints.yaml").write_text(constraints_text, encoding="utf-8")


def test_inheritance_merge_is_deterministic(tmp_path: Path) -> None:
    root = tmp_path / "packs"
    _seed_pack(root / "base", pack_id="base", system_text="BASE")
    _seed_pack(root / "mid", pack_id="mid", extends="base", constraints_text="rules: [mid]\n")
    _seed_pack(root / "leaf", pack_id="leaf", extends="mid", system_text="LEAF")
    first = resolve_pack(root / "leaf", packs_root=root)
    second = resolve_pack(root / "leaf", packs_root=root)
    assert first.resolved_files == second.resolved_files
    assert first.inheritance_chain == second.inheritance_chain


def test_missing_required_files_returns_deterministic_error_code(tmp_path: Path) -> None:
    broken = tmp_path / "broken"
    broken.mkdir(parents=True, exist_ok=True)
    (broken / "pack.json").write_text(json.dumps({"id": "x", "version": "1.0.0"}), encoding="utf-8")
    (broken / "system.txt").write_text("x", encoding="utf-8")
    with pytest.raises(PackValidationError) as exc:
        resolve_pack(broken)
    assert exc.value.code == "E_PACK_REQUIRED_MISSING"


def test_resolved_pack_digest_is_stable(tmp_path: Path) -> None:
    root = tmp_path / "packs"
    _seed_pack(root / "base", pack_id="base", system_text="BASE")
    resolved = resolve_pack(root / "base", packs_root=root)
    assert resolved_pack_digest(resolved) == resolved_pack_digest(resolved)

