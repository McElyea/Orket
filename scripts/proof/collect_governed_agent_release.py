"""Collect core 0.6.0 release evidence and verify packaged source identity."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger  # noqa: E402

OUTPUT = ROOT / "benchmarks/results/releases/0.6.0"


def _wheel_sources(path: Path, external: Path) -> dict:
    checked = []
    mismatches = []
    sdk_entries = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.startswith("orket_extension_sdk/"):
                sdk_entries.append(name)
            if not name.endswith((".py", ".json", ".typed")) or not name.startswith(
                ("orket/", "orket_extension_sdk/", "orket_governed_local_agent/")
            ):
                continue
            source = (external if name.startswith("orket_governed_local_agent/") else ROOT) / name
            checked.append(name)
            if not source.is_file() or source.read_bytes() != archive.read(name):
                mismatches.append(name)
    if path.name.startswith("orket-") and sdk_entries:
        mismatches.append("core unexpectedly owns SDK namespace")
    return {"checked_package_files": checked, "mismatches": mismatches, "sdk_namespace_entries": len(sdk_entries)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-root", required=True, type=Path)
    parser.add_argument("--extension-root", required=True, type=Path)
    args = parser.parse_args()
    artifacts = sorted(args.artifacts_root.resolve().glob("*-dist/*"))
    if len(artifacts) != 6:
        raise ValueError("Expected exactly three wheels and three source distributions")
    snapshots = {}
    for name in ("acceptance", "compatibility"):
        payload = json.loads((ROOT / f"benchmarks/results/governed_agent/{name}.json").read_text(encoding="utf-8"))
        payload.pop("diff_ledger", None)
        write_payload_with_diff_ledger(OUTPUT / f"{name}.json", payload)
        snapshots[name] = payload
    rows = []
    for artifact in artifacts:
        row = {"filename": artifact.name, "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
               "bytes": artifact.stat().st_size}
        if artifact.suffix == ".whl":
            row["source_verification"] = _wheel_sources(artifact, args.extension_root.resolve())
        elif artifact.name.startswith("orket-"):
            with tarfile.open(artifact) as archive:
                row["core_sdist_sdk_entries"] = sum("/orket_extension_sdk/" in n for n in archive.getnames())
        rows.append(row)
    observed = {row["sha256"] for row in rows}
    proven = {row["sha256"] for row in snapshots["acceptance"]["build"]["artifacts"]}
    accepted = snapshots["acceptance"]["observed_result"] == snapshots["compatibility"]["observed_result"] == "success"
    accepted = accepted and observed == proven and all(
        not row.get("source_verification", {}).get("mismatches") and not row.get("core_sdist_sdk_entries", 0)
        for row in rows)
    payload = {"schema_version": "governed_agent_release_artifacts.v1", "proof_mode": "structural",
               "observed_path": "primary", "observed_result": "success" if accepted else "failure",
               "artifacts": rows, "acceptance_artifacts_match": observed == proven,
               "source_basis": "Package source/resource bytes compared to release worktree; Git tags bind final source commit.",
               "external_source": str(args.extension_root.resolve()),
               "core_tag": "v0.6.0", "sdk_tag": "sdk-v0.6.0", "external_tag": "v0.2.0"}
    write_payload_with_diff_ledger(OUTPUT / "artifacts.json", payload)
    shutil.copy2(snapshots["acceptance"]["log"], OUTPUT / "acceptance.log")
    print(json.dumps({"result": payload["observed_result"], "output": str(OUTPUT),
                      "artifacts": len(rows)}, indent=2))
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
