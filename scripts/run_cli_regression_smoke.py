from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List


def _run(cmd: List[str], *, cwd: Path, env: Dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    return subprocess.run(cmd, cwd=cwd, env=merged_env, capture_output=True, text=True, check=False)


def _json_from_stdout(stdout: str) -> Dict[str, Any]:
    text = str(stdout or "").strip()
    if not text:
        return {}
    return json.loads(text)


def _git(repo: Path, *args: str) -> None:
    proc = _run(["git", *args], cwd=repo)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stdout}\n{proc.stderr}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic CLI regression smoke for init/api/refactor.")
    parser.add_argument("--out", default="benchmarks/results/cli_regression_smoke.json")
    args = parser.parse_args()

    module_entry = [sys.executable, "-m", "orket.interfaces.orket_bundle_cli"]
    run_env = {
        "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
    }
    events: List[Dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="orket_cli_smoke_") as tmp:
        root = Path(tmp)
        scaffold_dir = root / "scaffold"
        init = _run(
            [*module_entry, "init", "minimal-node", "smokeapp", "--dir", str(scaffold_dir), "--json"],
            cwd=Path.cwd(),
            env=run_env,
        )
        events.append(
            {
                "step": "init",
                "returncode": init.returncode,
                "result": _json_from_stdout(init.stdout) if init.returncode == 0 else {},
                "stderr": init.stderr.strip(),
            }
        )
        if init.returncode != 0:
            raise RuntimeError(f"init failed: {init.stdout}\n{init.stderr}")

        repo = root / "repo"
        (repo / "src" / "routes").mkdir(parents=True, exist_ok=True)
        (repo / "src" / "controllers").mkdir(parents=True, exist_ok=True)
        (repo / "src" / "routes" / "index.js").write_text(
            "function buildRouter() {\n"
            "  const router = { get(){}, post(){} };\n"
            "  return router;\n"
            "}\n\n"
            "const router = buildRouter();\n"
            "module.exports = router;\n",
            encoding="utf-8",
        )
        (repo / "verify.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        (repo / "orket.config.json").write_text(
            json.dumps({"verify": {"profiles": {"default": {"commands": ["python verify.py"]}}}}, indent=2) + "\n",
            encoding="utf-8",
        )

        _git(repo, "init")
        _git(repo, "config", "user.email", "cli-smoke@example.com")
        _git(repo, "config", "user.name", "CLI Smoke")
        _git(repo, "add", ".")
        _git(repo, "commit", "-m", "seed")

        api_dry = _run(
            [*module_entry, "api", "add", "users", "--schema", "id:int,name:string", "--scope", "./src", "--dry-run", "--json"],
            cwd=repo,
            env=run_env,
        )
        events.append({"step": "api_dry_run", "returncode": api_dry.returncode, "result": _json_from_stdout(api_dry.stdout)})
        if api_dry.returncode != 0:
            raise RuntimeError(f"api dry-run failed: {api_dry.stdout}\n{api_dry.stderr}")

        api_apply = _run(
            [*module_entry, "api", "add", "users", "--schema", "id:int,name:string", "--scope", "./src", "--yes", "--json"],
            cwd=repo,
            env=run_env,
        )
        events.append({"step": "api_apply", "returncode": api_apply.returncode, "result": _json_from_stdout(api_apply.stdout)})
        if api_apply.returncode != 0:
            raise RuntimeError(f"api apply failed: {api_apply.stdout}\n{api_apply.stderr}")

        _git(repo, "add", ".")
        _git(repo, "commit", "-m", "apply users route")

        api_noop = _run(
            [*module_entry, "api", "add", "users", "--schema", "id:int,name:string", "--scope", "./src", "--yes", "--json"],
            cwd=repo,
            env=run_env,
        )
        events.append({"step": "api_noop", "returncode": api_noop.returncode, "result": _json_from_stdout(api_noop.stdout)})
        if api_noop.returncode != 0:
            raise RuntimeError(f"api noop failed: {api_noop.stdout}\n{api_noop.stderr}")

        ref_dry = _run(
            [*module_entry, "refactor", "rename users to members", "--scope", "./src", "--dry-run", "--json"],
            cwd=repo,
            env=run_env,
        )
        events.append({"step": "refactor_dry_run", "returncode": ref_dry.returncode, "result": _json_from_stdout(ref_dry.stdout)})
        if ref_dry.returncode != 0:
            raise RuntimeError(f"refactor dry-run failed: {ref_dry.stdout}\n{ref_dry.stderr}")

        ref_apply = _run(
            [*module_entry, "refactor", "rename users to members", "--scope", "./src", "--yes", "--json"],
            cwd=repo,
            env=run_env,
        )
        events.append({"step": "refactor_apply", "returncode": ref_apply.returncode, "result": _json_from_stdout(ref_apply.stdout)})
        if ref_apply.returncode != 0:
            raise RuntimeError(f"refactor apply failed: {ref_apply.stdout}\n{ref_apply.stderr}")

    payload = {
        "ok": True,
        "status": "PASS",
        "events": events,
    }
    out_path = Path(str(args.out))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out_path), "event_count": len(events)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
