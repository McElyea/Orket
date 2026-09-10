"""Exercise built legacy/current package combinations and the namespace-owner upgrade."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger  # noqa: E402

OUTPUT = ROOT / "benchmarks/results/governed_agent/compatibility.json"
LEGACY_REF = "v0.5.9"


def _run(command: list[str], directory: Path, *, required: bool = True) -> dict:
    result = subprocess.run(command, cwd=directory, capture_output=True, text=True, check=False,
                            env={**os.environ, "ORKET_DISABLE_SANDBOX": "1"}, timeout=300)
    record = {"command": command, "exit_code": result.returncode,
              "stdout": result.stdout, "stderr": result.stderr}
    if required and result.returncode:
        raise RuntimeError(json.dumps(record))
    return record


def _build_old(directory: Path) -> tuple[Path, Path, Path]:
    archive = directory / "legacy.tar"
    # Archive package inputs only; the historical tree also tracks unrelated
    # temporary absolute symlinks, which must never be extracted.
    _run(["git", "archive", "--format=tar", f"--output={archive}", LEGACY_REF,
          "pyproject.toml", "README.md", "LICENSE", "orket", "orket_extension_sdk",
          "docs/templates/external_extension"], ROOT)
    source = directory / "legacy-source"
    source.mkdir()
    with tarfile.open(archive) as contents:
        contents.extractall(source, filter="data")
    legacy_extension = source / "docs/templates/external_extension"
    for name, project in (("legacy-core", source), ("legacy-extension", legacy_extension)):
        record = _run([sys.executable, "-m", "build", "--wheel", "--sdist", "--outdir",
                       str(directory / name), str(project)], directory)
        (directory / f"{name}-build.log").write_text(record["stdout"] + record["stderr"], encoding="utf-8")
    with tarfile.open(next((directory / "legacy-extension").glob("*.tar.gz"))) as contents:
        contents.extractall(directory / "legacy-extracted", filter="data")
    return (next((directory / "legacy-core").glob("*.whl")),
            next((directory / "legacy-extension").glob("*.whl")),
            next((directory / "legacy-extracted").iterdir()))


def _probe(python: str, directory: Path) -> dict:
    code = (
        "import json,importlib.metadata as m,orket,orket_extension_sdk as sdk; "
        "owners={d.metadata['Name'] for d in m.distributions() "
        "if any(str(p).startswith('orket_extension_sdk/') for p in (d.files or []))}; "
        "print(json.dumps({'core_version':m.version('orket'),'sdk_version':sdk.__version__,"
        "'core_path':orket.__file__,'sdk_path':sdk.__file__,'sdk_owners':sorted(owners)}))"
    )
    return json.loads(_run([python, "-I", "-c", code], directory)["stdout"])


def _validate(python: str, target: Path, directory: Path) -> dict:
    result = _run([python, "-I", "-m", "orket.interfaces.orket_bundle_cli", "ext", "validate",
                   str(target), "--strict", "--json"], directory, required=False)
    try:
        result["validation"] = json.loads(result["stdout"])
    except ValueError:
        result["validation"] = None
    return result


def _matrix(args, directory: Path) -> dict:
    old_core, old_extension, old_root = _build_old(directory)
    _run([sys.executable, "-m", "venv", str(directory / "venv")], directory)
    python = str(directory / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
    install = [python, "-m", "pip", "install"]
    _run([*install, str(old_core)], directory)
    old = {"identity": _probe(python, directory), "validation": _validate(python, old_root, directory)}
    missing_packaging = "ModuleNotFoundError: No module named 'packaging'" in old["validation"]["stderr"]
    if missing_packaging:
        old["observed_path"], old["observed_result"] = "blocked", "environment blocker"
        old["diagnostic_dependency_install"] = _run([*install, "packaging"], directory)
        old["diagnostic_validation"] = _validate(python, old_root, directory)
    old["agent_validation"] = _validate(python, args.extension_root, directory)
    _run([*install, str(args.sdk.resolve())], directory)
    mixed = {"identity": _probe(python, directory), "validation": _validate(python, args.extension_root, directory)}
    # Removing a legacy core also removes files it owned in the SDK namespace.
    # Reinstall the standalone SDK last so its RECORD and installed bytes agree.
    _run([*install, "--upgrade", str(args.core.resolve())], directory)
    _run([*install, "--force-reinstall", "--no-deps", str(args.sdk.resolve()), str(old_extension)], directory)
    current = {"identity": _probe(python, directory), "pip_check": _run([python, "-m", "pip", "check"], directory),
               "legacy_validation": _validate(python, old_root, directory),
               "agent_validation": _validate(python, args.extension_root, directory)}
    smoke = "from companion_extension.workload import run; r=run(None,{'message':'legacy'}); assert r.ok; print(r.model_dump_json())"
    current["legacy_workload"] = _run([python, "-I", "-c", smoke], directory)
    old_checked = old["validation"]["exit_code"] == 0 or (
        missing_packaging and old["diagnostic_validation"]["exit_code"] == 0)
    old_checked = old_checked and old["identity"]["sdk_owners"] == ["orket"]
    old_checked = old_checked and old["agent_validation"]["exit_code"] != 0 and (
        old["agent_validation"]["validation"] is not None)
    mixed_detected = len(mixed["identity"]["sdk_owners"]) == 2
    new_ok = all(current[key]["exit_code"] == 0 for key in ("legacy_validation", "agent_validation", "legacy_workload"))
    new_ok = new_ok and current["identity"]["sdk_owners"] == ["orket-extension-sdk"]
    artifacts = [old_core, old_extension, args.core, args.sdk]
    return {"schema_version": "governed_agent_compatibility.v1", "proof_mode": "live",
            "observed_path": "primary", "observed_result": "success" if old_checked and mixed_detected and new_ok else "failure",
            "legacy_ref": LEGACY_REF, "old_host_bundled_sdk": old,
            "old_host_new_sdk": {"compatibility": "unsupported_duplicate_namespace_ownership", **mixed},
            "upgraded_host_new_sdk": current,
            "artifacts": [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in artifacts],
            "limitations": ["Legacy template echo validates the public generic workload; it does not invoke a model.",
                            "Successful matrix collection does not change the legacy baseline's missing-dependency blocker.",
                            "Old host/new SDK is an unsupported combination even if author validation passes.",
                            "Matching current agent execution is proved by the separate installed live acceptance report."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--extension-root", type=Path, required=True)
    args = parser.parse_args()
    args.extension_root = args.extension_root.resolve()
    parent = ROOT / ".tmp/governed-agent-compatibility"
    parent.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="execution-", dir=parent))
    try:
        payload = _matrix(args, directory)
    except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError, tarfile.TarError) as exc:
        payload = {"observed_path": "blocked", "observed_result": "failure", "error": str(exc)}
    payload["evidence_directory"] = str(directory)
    write_payload_with_diff_ledger(OUTPUT, payload)
    print(json.dumps({"output": str(OUTPUT), "result": payload["observed_result"], "evidence": str(directory)}, indent=2))
    return 0 if payload["observed_result"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
