from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.reforger.modes import ModeValidationError, load_mode
from orket.reforger.packs import PackValidationError, resolve_pack


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_pack(
    pack_dir: Path,
    *,
    pack_id: str,
    version: str = "1.0.0",
    extends: str | None = None,
    system_name: str = "system.txt",
    system_text: str = "base system",
    constraints_text: str = "rules: []\n",
    developer_text: str | None = None,
    examples_text: str | None = None,
) -> None:
    pack_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {"id": pack_id, "version": version}
    if extends is not None:
        payload["extends"] = extends
    _write_json(pack_dir / "pack.json", payload)
    (pack_dir / system_name).write_text(system_text, encoding="utf-8")
    (pack_dir / "constraints.yaml").write_text(constraints_text, encoding="utf-8")
    if developer_text is not None:
        (pack_dir / "developer.txt").write_text(developer_text, encoding="utf-8")
    if examples_text is not None:
        (pack_dir / "examples.jsonl").write_text(examples_text, encoding="utf-8")


def test_resolve_pack_inheritance_child_overlay_wins(tmp_path: Path) -> None:
    packs_root = tmp_path / "packs"
    base = packs_root / "base_pack"
    child = packs_root / "child_pack"

    _seed_pack(
        base,
        pack_id="base_pack",
        system_text="BASE",
        constraints_text="scope: base\n",
        developer_text="base dev",
    )
    _seed_pack(
        child,
        pack_id="child_pack",
        extends="base_pack",
        system_name="system.md",
        system_text="CHILD",
        constraints_text="scope: child\n",
    )

    resolved = resolve_pack(child, packs_root=packs_root)
    assert [str(path.name) for path in resolved.inheritance_chain] == ["base_pack", "child_pack"]
    assert resolved.metadata.pack_id == "child_pack"
    assert resolved.resolved_files["constraints.yaml"] == "scope: child\n"
    assert resolved.resolved_files["system.md"] == "CHILD"
    assert "system.txt" not in resolved.resolved_files
    assert resolved.resolved_files["developer.txt"] == "base dev"


def test_resolve_pack_missing_required_files_is_deterministic_error(tmp_path: Path) -> None:
    broken = tmp_path / "broken"
    broken.mkdir(parents=True, exist_ok=True)
    _write_json(broken / "pack.json", {"id": "broken", "version": "1.0.0"})
    (broken / "system.txt").write_text("ok", encoding="utf-8")

    with pytest.raises(PackValidationError) as exc:
        resolve_pack(broken)
    assert "Missing required pack files (constraints.yaml)" in str(exc.value)


def test_resolve_pack_cycle_raises(tmp_path: Path) -> None:
    packs_root = tmp_path / "packs"
    pack_a = packs_root / "a"
    pack_b = packs_root / "b"
    _seed_pack(pack_a, pack_id="a", extends="b")
    _seed_pack(pack_b, pack_id="b", extends="a")

    with pytest.raises(PackValidationError) as exc:
        resolve_pack(pack_a, packs_root=packs_root)
    assert "Detected cyclic pack inheritance" in str(exc.value)


def test_load_mode_validates_required_schema(tmp_path: Path) -> None:
    yaml = pytest.importorskip("yaml")
    assert yaml is not None
    mode_file = tmp_path / "truth_or_refuse.yaml"
    mode_file.write_text(
        "\n".join(
            [
                "mode_id: truth_or_refuse",
                "description: test mode",
                "hard_rules:",
                "  - never fabricate",
                "soft_rules:",
                "  - stay concise",
                "rubric:",
                "  relevance: 0.4",
                "  compliance: 0.6",
                "required_outputs:",
                "  - refusal_reason",
                "suite_ref: suites/truth_or_refuse",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    mode = load_mode(mode_file)
    assert mode.mode_id == "truth_or_refuse"
    assert mode.hard_rules == ("never fabricate",)
    assert tuple(mode.rubric.keys()) == ("compliance", "relevance")


def test_load_mode_rejects_invalid_fields(tmp_path: Path) -> None:
    yaml = pytest.importorskip("yaml")
    assert yaml is not None
    mode_file = tmp_path / "bad.yaml"
    mode_file.write_text(
        "\n".join(
            [
                "mode_id: bad",
                "description: bad mode",
                "hard_rules: not-a-list",
                "soft_rules:",
                "  - okay",
                "rubric:",
                "  score: 1.0",
                "required_outputs:",
                "  - refusal_reason",
                "suite_ref: suites/bad",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ModeValidationError) as exc:
        load_mode(mode_file)
    assert "hard_rules" in str(exc.value)

