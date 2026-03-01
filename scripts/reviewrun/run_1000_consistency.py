from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orket.application.review.models import ReviewSnapshot, SnapshotBounds
from orket.application.review.run_service import ReviewRunService


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    return proc.stdout.decode("utf-8", errors="replace").strip()


def _seed_repo_for_constants_diff(repo: Path) -> tuple[str, str]:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "tester")

    (repo / "app").mkdir(parents=True, exist_ok=True)
    base_content = (
        'APP_NAME = "DemoApp"\n'
        'VERSION = "0.1.0"\n'
        "\n"
        "def get_app_name() -> str:\n"
        "    return APP_NAME\n"
    )
    (repo / "app" / "constants.py").write_text(base_content, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base constants")
    base = _git(repo, "rev-parse", "HEAD")

    lines = [
        'APP_NAME = "DemoApp"',
        'VERSION = "0.1.0"',
        "",
        "# Feature flags (generated)",
    ]
    lines.extend([f"FLAG_{idx:03d} = True" for idx in range(1, 51)])
    lines.extend(
        [
            "",
            "def get_app_name() -> str:",
            "    return APP_NAME",
            "",
        ]
    )
    (repo / "app" / "constants.py").write_text("\n".join(lines), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "head constants with flags")
    head = _git(repo, "rev-parse", "HEAD")
    return base, head


def _seed_repo_for_secrets_sha1_diff(repo: Path) -> tuple[str, str]:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "tester")

    (repo / "app").mkdir(parents=True, exist_ok=True)
    (repo / "app" / "secrets.py").write_text(
        "def get_api_key() -> str:\n    raise NotImplementedError()\n",
        encoding="utf-8",
    )
    (repo / "app" / "crypto.py").write_text(
        "import hashlib\n\n"
        "def digest(s: str) -> str:\n"
        "    return hashlib.sha1(s.encode()).hexdigest()\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base secrets+crypto")
    base = _git(repo, "rev-parse", "HEAD")

    (repo / "app" / "secrets.py").write_text(
        'API_KEY = "sk-live-hardcoded"\n\n'
        "def get_api_key() -> str:\n"
        "    return API_KEY\n",
        encoding="utf-8",
    )
    (repo / "app" / "crypto.py").write_text(
        "import hashlib\n\n"
        "def digest(s: str) -> str:\n"
        "    # legacy\n"
        "    return hashlib.sha1(s.encode()).hexdigest()\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "head secrets+crypto")
    head = _git(repo, "rev-parse", "HEAD")
    return base, head


def _seed_repo_for_auth_insecure_diff(repo: Path) -> tuple[str, str]:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "tester")

    (repo / "app").mkdir(parents=True, exist_ok=True)
    (repo / "tests").mkdir(parents=True, exist_ok=True)
    (repo / "app" / "auth.py").write_text("", encoding="utf-8")
    (repo / "tests" / "test_auth.py").write_text(
        "from app.auth import hash_password\n\n"
        "def test_hash():\n"
        "    assert hash_password('x') != ''\n",
        encoding="utf-8",
    )
    (repo / "README.md").write_text(
        "Installation\nRun the following:\n\npip install -r requirements.txt\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base auth")
    base = _git(repo, "rev-parse", "HEAD")

    (repo / "app" / "auth.py").write_text(
        "import os\n"
        "import hashlib\n\n"
        "SECRET_KEY = \"hardcoded-secret\"\n\n"
        "def hash_password(password: str) -> str:\n"
        "    return hashlib.md5(password.encode()).hexdigest()\n\n"
        "def authenticate(user, password):\n"
        "    if user.password_hash == hash_password(password):\n"
        "        return True\n"
        "    return False\n\n"
        "def load_config():\n"
        "    return {\n"
        "        \"db_url\": os.getenv(\"DATABASE_URL\"),\n"
        "        \"debug\": True\n"
        "    }\n",
        encoding="utf-8",
    )
    (repo / "tests" / "test_auth.py").write_text(
        "from app.auth import hash_password\n\n"
        "def test_hash():\n"
        "    result = hash_password(\"x\")\n"
        "    assert result is not None\n\n"
        "def test_auth_smoke():\n"
        "    class User:\n"
        "        password_hash = hash_password(\"x\")\n"
        "    assert True\n",
        encoding="utf-8",
    )
    (repo / "README.md").write_text(
        "Installation\nRun the following:\n\npip install -r requirements.txt\n\n"
        "## Development Mode\nSet DEBUG=true to enable verbose logging.\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "head auth insecure")
    head = _git(repo, "rev-parse", "HEAD")
    return base, head


def _seed_repo_for_math_parse_int_diff(repo: Path) -> tuple[str, str]:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "tester")

    (repo / "app").mkdir(parents=True, exist_ok=True)
    (repo / "app" / "math_utils.py").write_text(
        "def clamp(x: int, lo: int, hi: int) -> int:\n"
        "    if x < lo:\n"
        "        return lo\n"
        "    if x > hi:\n"
        "        return hi\n"
        "    return x\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base math")
    base = _git(repo, "rev-parse", "HEAD")

    (repo / "app" / "math_utils.py").write_text(
        "def clamp(x: int, lo: int, hi: int) -> int:\n"
        "    if x < lo:\n"
        "        return lo\n"
        "    if x > hi:\n"
        "        return hi\n"
        "    return x\n\n"
        "def parse_int(s: str) -> int:\n"
        "    # accepts \" 42 \" and \"+42\"\n"
        "    s2 = s.strip()\n"
        "    if s2.startswith(\"+\"):\n"
        "        s2 = s2[1:]\n"
        "    return int(s2)\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "head math parse_int")
    head = _git(repo, "rev-parse", "HEAD")
    return base, head


def _signature_from_run(run_dir: Path, run_result: Dict[str, Any]) -> Dict[str, Any]:
    deterministic = json.loads((run_dir / "deterministic_decision.json").read_text(encoding="utf-8"))
    snapshot = json.loads((run_dir / "snapshot.json").read_text(encoding="utf-8"))
    return {
        "snapshot_digest": str(run_result.get("snapshot_digest") or ""),
        "policy_digest": str(run_result.get("policy_digest") or ""),
        "decision": str(deterministic.get("decision") or ""),
        "findings": list(deterministic.get("findings") or []),
        "executed_checks": list(deterministic.get("executed_checks") or []),
        "deterministic_lane_version": str(deterministic.get("deterministic_lane_version") or ""),
        "truncation": dict(snapshot.get("truncation") or {}),
    }


def _strict_policy_for_scenario(scenario: str) -> Dict[str, Any]:
    if scenario == "secrets_sha1":
        patterns = [
            r"API_KEY\s*=\s*\"",
            r"hashlib\.sha1\(",
        ]
    elif scenario == "auth_insecure":
        patterns = [
            r"SECRET_KEY\s*=\s*\"",
            r"hashlib\.md5\(",
            r"\"debug\"\s*:\s*True",
        ]
    elif scenario == "math_parse_int":
        patterns = [
            r"TODO|FIXME",
        ]
    else:
        patterns = [
            r"FLAG_\d{3}\s*=\s*True",
            r"VERSION\s*=\s*\"",
        ]
    return {
        "deterministic": {
            "checks": {
                "forbidden_patterns": patterns,
                "test_hint_required_roots": ["app/"],
                "test_hint_test_roots": ["tests/"],
            }
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ReviewRun diff consistency loop.")
    parser.add_argument("--runs", type=int, default=1000, help="Number of ReviewRun iterations.")
    parser.add_argument(
        "--out",
        type=str,
        default="benchmarks/results/reviewrun_consistency_1000.json",
        help="Output report path.",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default="workspace/default/reviewrun_consistency_tmp",
        help="Workspace root for generated run artifacts.",
    )
    parser.add_argument(
        "--keep-fixture",
        action="store_true",
        help="Keep temporary seeded fixture repo/workspace on disk.",
    )
    parser.add_argument(
        "--keep-runs",
        action="store_true",
        help="Do not delete generated review run artifact folders.",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default="constants_flags",
        choices=["constants_flags", "secrets_sha1", "auth_insecure", "math_parse_int", "truncation_bounds"],
        help="Seeded diff scenario.",
    )
    args = parser.parse_args()

    if args.runs <= 0:
        raise ValueError("--runs must be positive")

    fixture_root = Path(tempfile.mkdtemp(prefix="orket_reviewrun_constants_"))
    fixture_repo = fixture_root / "repo"
    workspace = Path(args.workspace).resolve()
    if workspace.exists() and not args.keep_runs:
        shutil.rmtree(workspace, ignore_errors=True)
    workspace.mkdir(parents=True, exist_ok=True)

    if args.scenario == "constants_flags":
        base_ref, head_ref = _seed_repo_for_constants_diff(fixture_repo)
    elif args.scenario == "secrets_sha1":
        base_ref, head_ref = _seed_repo_for_secrets_sha1_diff(fixture_repo)
    elif args.scenario == "auth_insecure":
        base_ref, head_ref = _seed_repo_for_auth_insecure_diff(fixture_repo)
    elif args.scenario == "math_parse_int":
        base_ref, head_ref = _seed_repo_for_math_parse_int_diff(fixture_repo)
    else:
        base_ref, head_ref = _seed_repo_for_constants_diff(fixture_repo)
    service = ReviewRunService(workspace=workspace)
    bounds = SnapshotBounds()
    if args.scenario == "truncation_bounds":
        bounds = SnapshotBounds(max_diff_bytes=300)

    truncation_check: Dict[str, Any] | None = None
    if args.scenario == "truncation_bounds":
        unbounded_run = service.run_diff(
            repo_root=fixture_repo,
            base_ref=base_ref,
            head_ref=head_ref,
            bounds=SnapshotBounds(max_diff_bytes=1_000_000),
        ).to_dict()
        truncated_run = service.run_diff(
            repo_root=fixture_repo,
            base_ref=base_ref,
            head_ref=head_ref,
            bounds=SnapshotBounds(max_diff_bytes=300),
        ).to_dict()
        truncated_snapshot = json.loads(
            (Path(str(truncated_run["artifact_dir"])) / "snapshot.json").read_text(encoding="utf-8")
        )
        truncation = dict(truncated_snapshot.get("truncation") or {})
        truncation_check = {
            "unbounded_snapshot_digest": str(unbounded_run.get("snapshot_digest") or ""),
            "truncated_snapshot_digest": str(truncated_run.get("snapshot_digest") or ""),
            "digests_differ": str(unbounded_run.get("snapshot_digest") or "")
            != str(truncated_run.get("snapshot_digest") or ""),
            "diff_truncated": bool(truncation.get("diff_truncated") or False),
            "diff_bytes_original": int(truncation.get("diff_bytes_original") or 0),
            "diff_bytes_kept": int(truncation.get("diff_bytes_kept") or 0),
            "ok": bool(truncation.get("diff_truncated") or False)
            and (
                str(unbounded_run.get("snapshot_digest") or "")
                != str(truncated_run.get("snapshot_digest") or "")
            ),
        }

    mismatch: Dict[str, Any] | None = None
    baseline_signature: Dict[str, Any] | None = None
    baseline_run_id = ""
    checked = 0

    default_run = service.run_diff(
        repo_root=fixture_repo,
        base_ref=base_ref,
        head_ref=head_ref,
        bounds=bounds,
    ).to_dict()
    default_run_dir = Path(str(default_run["artifact_dir"]))
    default_signature = _signature_from_run(run_dir=default_run_dir, run_result=default_run)

    strict_policy = _strict_policy_for_scenario(args.scenario)
    strict_run = service.run_diff(
        repo_root=fixture_repo,
        base_ref=base_ref,
        head_ref=head_ref,
        bounds=bounds,
        cli_policy_overrides=strict_policy,
    ).to_dict()
    strict_run_dir = Path(str(strict_run["artifact_dir"]))
    strict_signature = _signature_from_run(run_dir=strict_run_dir, run_result=strict_run)
    strict_snapshot = json.loads((strict_run_dir / "snapshot.json").read_text(encoding="utf-8"))
    strict_policy_payload = json.loads((strict_run_dir / "policy_resolved.json").read_text(encoding="utf-8"))
    strict_replay_run = service.replay(
        repo_root=fixture_repo,
        snapshot=ReviewSnapshot.from_dict(strict_snapshot),
        resolved_policy_payload={k: v for k, v in strict_policy_payload.items() if k != "policy_digest"},
    ).to_dict()
    strict_replay_dir = Path(str(strict_replay_run["artifact_dir"]))
    strict_replay_signature = _signature_from_run(run_dir=strict_replay_dir, run_result=strict_replay_run)

    strict_replay_parity = strict_signature == strict_replay_signature

    for iteration in range(1, int(args.runs) + 1):
        run = service.run_diff(
            repo_root=fixture_repo,
            base_ref=base_ref,
            head_ref=head_ref,
            bounds=bounds,
        ).to_dict()
        run_dir = Path(str(run["artifact_dir"]))
        signature = _signature_from_run(run_dir=run_dir, run_result=run)
        if baseline_signature is None:
            baseline_signature = signature
            baseline_run_id = str(run["run_id"])
        elif signature != baseline_signature:
            mismatch = {
                "iteration": iteration,
                "run_id": str(run["run_id"]),
                "expected": baseline_signature,
                "actual": signature,
            }
            checked = iteration
            break
        checked = iteration

    report = {
        "ok": mismatch is None and strict_replay_parity,
        "consistency": {
            "runs_requested": int(args.runs),
            "runs_checked": checked,
            "baseline_run_id": baseline_run_id,
            "baseline_signature": baseline_signature or {},
            "mismatch": mismatch,
        },
        "default_run": {
            "run_id": str(default_run.get("run_id") or ""),
            "artifact_dir": str(default_run.get("artifact_dir") or ""),
            "signature": default_signature,
        },
        "strict_run": {
            "run_id": str(strict_run.get("run_id") or ""),
            "artifact_dir": str(strict_run.get("artifact_dir") or ""),
            "signature": strict_signature,
            "strict_policy": strict_policy,
        },
        "strict_replay": {
            "run_id": str(strict_replay_run.get("run_id") or ""),
            "artifact_dir": str(strict_replay_run.get("artifact_dir") or ""),
            "signature": strict_replay_signature,
            "parity_with_strict": strict_replay_parity,
        },
        "truncation_check": truncation_check,
        "base_ref": base_ref,
        "head_ref": head_ref,
        "scenario": args.scenario,
        "fixture_repo": str(fixture_repo),
        "workspace": str(workspace),
        "contract_version": "reviewrun_consistency_check_v1",
    }

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    if not args.keep_fixture:
        shutil.rmtree(fixture_root, ignore_errors=True)
    if not args.keep_runs and mismatch is None and strict_replay_parity:
        shutil.rmtree(workspace, ignore_errors=True)

    return 0 if (mismatch is None and strict_replay_parity) else 1


if __name__ == "__main__":
    raise SystemExit(main())
