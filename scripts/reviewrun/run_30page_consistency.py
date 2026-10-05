"""Repeat a self-contained 30-page fixture, recovered from history or newly generated."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from orket.application.review.models import SnapshotBounds
from orket.application.review.run_service import ReviewRunService
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.reviewrun.make_30page_fixture_repo import make_repo, sh
from scripts.reviewrun.run_1000_consistency import _signature_from_run


def create_bundle(root: Path, bundle: Path, historical: dict | None) -> dict:
    if historical is None:
        info = make_repo()
        sh(["git", "bundle", "create", str(bundle), "--all"], info.repo_dir)
        return {"baseline_kind": "new-generated-baseline", "seed": 1337,
                "original_generated_repo": str(info.repo_dir), "base_ref": info.base_ref, "head_ref": info.head_ref,
                "generator_sha256": hashlib.sha256(Path(sys.modules[make_repo.__module__].__file__).read_bytes()).hexdigest()}
    base, head = historical["base_ref"], historical["head_ref"]
    if any(not re.fullmatch(r"[0-9a-f]{40}", value) for value in (base, head)):
        raise ValueError("Historical commit identities must be full Git SHA-1 values")
    recovery = root / "recovery"
    recovery.mkdir(exist_ok=False)
    environment = dict(os.environ, GIT_ALTERNATE_OBJECT_DIRECTORIES=str(Path(historical["repo_dir"]) / ".git/objects"))
    for args in (["init"], ["cat-file", "-e", base + "^{commit}"], ["cat-file", "-e", head + "^{commit}"],
                 ["update-ref", "refs/heads/recovered", head], ["symbolic-ref", "HEAD", "refs/heads/recovered"],
                 ["bundle", "create", str(bundle), "--all"]):
        subprocess.run(["git", *args], cwd=recovery, env=environment, check=True, capture_output=True)
    return {"baseline_kind": "recovered-historical-commits", "source_repo": historical["repo_dir"],
            "base_ref": base, "head_ref": head}


def fixture(root: Path, historical: dict | None = None) -> dict:
    manifest = root / "fixture.json"
    bundle = root / "fixture.bundle"
    repo = root / "fixture"
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if hashlib.sha256(bundle.read_bytes()).hexdigest() != data["bundle_sha256"]:
            raise ValueError("Retained fixture bundle checksum mismatch")
        if historical and any(data[key] != historical[key] for key in ("base_ref", "head_ref")):
            raise ValueError("Retained fixture does not match requested historical commits")
    else:
        root.mkdir(parents=True, exist_ok=True)
        if bundle.exists() or repo.exists():
            raise ValueError("Unowned fixture path exists without a manifest")
        data = create_bundle(root, bundle, historical)
        data["bundle_sha256"] = hashlib.sha256(bundle.read_bytes()).hexdigest()
        write_payload_with_diff_ledger(manifest, data)
    if not repo.exists():
        subprocess.run(["git", "clone", str(bundle), str(repo)], check=True, capture_output=True)
    sh(["git", "bundle", "verify", str(bundle)], repo)
    sh(["git", "fsck", "--full"], repo)
    if sh(["git", "rev-parse", "HEAD"], repo) != data["head_ref"] or sh(["git", "status", "--porcelain"], repo):
        raise ValueError("Fixture checkout drift; preserve it and restore a separate clone from the bundle")
    return data


def run(root: Path, output: Path, runs: int, policy_path: Path | None,
        historical_path: Path | None = None, expected_decision: str | None = None) -> int:
    historical = json.loads(historical_path.read_text(encoding="utf-8")) if historical_path else None
    data = fixture(root, historical)
    repo = root / "fixture"
    paths = historical["included_code_paths"] if historical else [
        p for p in sh(["git", "ls-tree", "-r", "--name-only", data["head_ref"]], repo).splitlines() if p.endswith(".py")]
    policy = json.loads(policy_path.read_text(encoding="utf-8")) if policy_path else {}
    policy.pop("policy_digest", None)
    if policy.get("model_assisted", {}).get("enabled", False):
        raise ValueError("This deterministic comparison does not admit model assistance")
    service = ReviewRunService(workspace=root / "reviews")
    baseline = None
    report = {"baseline_kind": data["baseline_kind"], "fixture": data, "paths": paths,
              "runs_requested": runs, "runs_checked": 0, "ok": False, "mismatch": None,
              "proof_mode": "live native deterministic ReviewRun; no model inference",
              "historical_report": str(historical_path) if historical_path else None,
              "expected_decision": expected_decision,
              "policy_source": str(policy_path) if policy_path else "runtime-default"}
    start = time.perf_counter()
    for index in range(1, runs + 1):
        result = service.run_files(repo_root=repo, ref=data["head_ref"], paths=paths,
            bounds=SnapshotBounds(**policy.get("bounds", {})), cli_policy_overrides=policy or None).to_dict()
        directory = Path(result["artifact_dir"])
        signature = _signature_from_run(run_dir=directory, run_result=result)
        baseline = signature if baseline is None else baseline
        if signature != baseline:
            report["mismatch"] = {"iteration": index, "signature": signature}
        if expected_decision is not None and signature["decision"] != expected_decision:
            report["mismatch"] = {"iteration": index, "reason": "unexpected_decision", "signature": signature}
        report.update(runs_checked=index, baseline=baseline, last_bundle=str(directory),
                      wall_seconds=time.perf_counter() - start, ok=index == runs and report["mismatch"] is None)
        if index == 1:
            report["first_bundle"] = str(directory)
        if index == 1 or index % 100 == 0 or report["mismatch"] or index == runs:
            write_payload_with_diff_ledger(output, report)
            print(json.dumps({"iteration": index, "mismatch": bool(report["mismatch"])}), flush=True)
        if report["mismatch"]:
            break
    return 0 if report["ok"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(".tmp/reviewrun-30page"))
    parser.add_argument("--out", type=Path, default=Path("benchmarks/staging/General/reviewrun_30page_consistency.json"))
    parser.add_argument("--runs", type=int, default=1000)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--historical-report", type=Path, help="Recover its exact commits without modifying the source repo")
    parser.add_argument("--expected-decision", choices=["pass", "changes_requested", "blocked"])
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")
    return run(args.root.resolve(), args.out.resolve(), args.runs, args.policy, args.historical_report, args.expected_decision)


if __name__ == "__main__":
    raise SystemExit(main())
