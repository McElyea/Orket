"""Real disposable Git repositories for standalone dependency command contracts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.governance.dependency_policy import POLICY_PATH, PROJECT_ROOT, load_dependency_policy


def make_repository(root: Path, files: dict[str, str | bytes], *, adapter_effect_bound: bool | None = True) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(["git", "init", "-q", str(root)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    source_policy = load_dependency_policy()
    for name, content in {"orket/__init__.py": "", **files}.items():
        target = root / name
        assert target.resolve().is_relative_to(root.resolve())
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = content.encode("utf-8") if isinstance(content, str) else content
        try:
            layer = source_policy.layer_for_module(".".join(Path(name).with_suffix("").parts))
        except ValueError:
            layer = None  # Deliberately unknown namespaces remain checker counterexamples.
        if adapter_effect_bound is not None and layer == "adapters":
            # Import fixtures conservatively admit effects; classification controls opt out.
            # Append so existing import-site line numbers and encoding declarations stay intact.
            raw += f"\nside_effecting = {adapter_effect_bound!r}\n".encode("ascii")
        target.write_bytes(raw)
    policy = root / "policy.json"
    policy.write_bytes(POLICY_PATH.read_bytes())
    return policy


def run_command(root: Path, *, exporter: bool = False) -> tuple[subprocess.CompletedProcess, dict]:
    script = "export_dependency_graph.py" if exporter else "check_dependency_direction.py"
    output = root / ("export.json" if exporter else "check.json")
    arguments = [
        sys.executable,
        str(PROJECT_ROOT / "scripts/governance" / script),
        "--root",
        str(root),
        "--policy",
        str(root / "policy.json"),
    ]
    arguments += (
        ["--out-json", str(output), "--out-md", str(root / "export.md")] if exporter else ["--out", str(output)]
    )
    process = subprocess.run(arguments, cwd=root, capture_output=True, text=True, timeout=30)
    assert output.is_file(), process.stdout + process.stderr
    return process, json.loads(output.read_text(encoding="utf-8"))
