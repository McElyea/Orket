from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _init_sdk_benchmark_extension_repo(repo_root: Path) -> None:
    manifest = {
        "manifest_version": "v0",
        "extension_id": "sdk.benchmark.extension",
        "extension_version": "0.1.0",
        "workloads": [
            {
                "workload_id": "sdk_benchmark_v1",
                "entrypoint": "sdk_benchmark_extension:run_workload",
                "required_capabilities": [],
            }
        ],
    }
    (repo_root / "extension.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (repo_root / "sdk_benchmark_extension.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import hashlib",
                "from pathlib import Path",
                "from orket_extension_sdk import ArtifactRef, WorkloadResult",
                "",
                "def run_workload(ctx, payload):",
                "    out_path = Path(ctx.output_dir) / 'benchmark.txt'",
                "    text = f\"seed={ctx.seed};label={payload.get('label', 'none')}\"",
                "    out_path.write_text(text, encoding='utf-8')",
                "    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()",
                "    return WorkloadResult(",
                "        ok=True,",
                "        output={'label': payload.get('label', 'none')},",
                "        artifacts=[ArtifactRef(path='benchmark.txt', digest_sha256=digest, kind='text')],",
                "    )",
            ]
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def test_run_extension_workload_baseline_emits_latency_report(tmp_path: Path) -> None:
    repo = tmp_path / "sdk_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _init_sdk_benchmark_extension_repo(repo)

    input_json = tmp_path / "input.json"
    input_json.write_text(json.dumps({"label": "baseline"}), encoding="utf-8")
    workspace = tmp_path / "workspace" / "default"
    output = tmp_path / "baseline_report.json"
    result = subprocess.run(
        [
            "python",
            "scripts/run_extension_workload_baseline.py",
            "--repo",
            str(repo),
            "--workload-id",
            "sdk_benchmark_v1",
            "--runs",
            "3",
            "--seed",
            "7",
            "--project-root",
            str(tmp_path),
            "--workspace",
            str(workspace),
            "--input-json",
            str(input_json),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "extension_workload_baseline.v1"
    assert payload["workload_id"] == "sdk_benchmark_v1"
    assert payload["runs"] == 3
    assert payload["input_config"]["seed"] == 7
    assert payload["input_config"]["label"] == "baseline"
    assert len(payload["run_rows"]) == 3
    assert payload["latency_ms"]["min"] >= 0.0
    assert payload["latency_ms"]["p50"] >= 0.0
    for row in payload["run_rows"]:
        assert Path(row["provenance_path"]).exists()
        assert Path(row["artifact_root"]).exists()
