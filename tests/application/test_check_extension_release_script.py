from __future__ import annotations

import json
import subprocess
import sys
import tarfile
from pathlib import Path


SCRIPT = Path("docs/templates/external_extension/scripts/check_release.py").resolve()


def _write_project(root: Path, *, version: str = "1.2.3") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "demo-extension"',
                f'version = "{version}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "extension.yaml").write_text(
        "\n".join(
            [
                "manifest_version: v0",
                "extension_id: demo.extension",
                f"extension_version: {version}",
                "workloads:",
                "  - workload_id: demo",
                "    entrypoint: demo_pkg.workload:run",
                "    required_capabilities: []",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_sdist(root: Path, *, version: str = "1.2.3", include_manifest: bool = True) -> Path:
    dist_dir = root / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    artifact = dist_dir / f"demo_extension-{version}.tar.gz"
    files = {
        "pyproject.toml": f"[project]\nname = \"demo-extension\"\nversion = \"{version}\"\n",
        "scripts/install.sh": "#!/usr/bin/env bash\n",
        "scripts/install.ps1": 'Write-Host "install"\n',
        "scripts/validate.sh": "#!/usr/bin/env bash\n",
        "scripts/validate.ps1": 'Write-Host "validate"\n',
        "scripts/build-release.sh": "#!/usr/bin/env bash\n",
        "scripts/build-release.ps1": 'Write-Host "build"\n',
        "scripts/verify-release.sh": "#!/usr/bin/env bash\n",
        "scripts/verify-release.ps1": 'Write-Host "verify"\n',
        "scripts/check_release.py": "print('ok')\n",
        "src/demo_pkg/__init__.py": "",
        "src/demo_pkg/workload.py": "def run(ctx, payload):\n    return payload\n",
        "tests/test_smoke.py": "def test_smoke():\n    assert True\n",
    }
    if include_manifest:
        files["extension.yaml"] = (
            "manifest_version: v0\n"
            "extension_id: demo.extension\n"
            f"extension_version: {version}\n"
            "workloads:\n"
            "  - workload_id: demo\n"
            "    entrypoint: demo_pkg.workload:run\n"
            "    required_capabilities: []\n"
        )

    with tarfile.open(artifact, "w:gz") as archive:
        for relative, content in files.items():
            full = root / relative
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")
            archive.add(full, arcname=f"demo_extension-{version}/{relative}")

    return artifact


def test_check_release_script_accepts_matching_tag_and_sdist(tmp_path: Path) -> None:
    """Layer: contract. Verifies the publish-surface checker accepts aligned source, artifact, and tag truth."""
    _write_project(tmp_path)
    _write_sdist(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-root",
            str(tmp_path),
            "--dist-dir",
            str(tmp_path / "dist"),
            "--tag",
            "v1.2.3",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert payload["ok"] is True
    assert payload["authoritative_artifact_family"] == "sdist"


def test_check_release_script_rejects_tag_mismatch(tmp_path: Path) -> None:
    """Layer: contract. Verifies the publish-surface checker fails closed on tag/version drift."""
    _write_project(tmp_path)
    _write_sdist(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-root",
            str(tmp_path),
            "--dist-dir",
            str(tmp_path / "dist"),
            "--tag",
            "v9.9.9",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "E_EXT_RELEASE_TAG_VERSION_MISMATCH"


def test_check_release_script_rejects_missing_manifest_in_sdist(tmp_path: Path) -> None:
    """Layer: contract. Verifies the publish-surface checker fails closed when the authoritative sdist drops manifest truth."""
    _write_project(tmp_path)
    _write_sdist(tmp_path, include_manifest=False)

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-root",
            str(tmp_path),
            "--dist-dir",
            str(tmp_path / "dist"),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "E_EXT_RELEASE_SDIST_LAYOUT_INCOMPLETE"
