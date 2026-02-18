from __future__ import annotations

import argparse
import json
import subprocess
import uuid
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one benchmark task through the live Orket card pipeline.")
    parser.add_argument("--task", required=True, help="Path to benchmark task JSON.")
    parser.add_argument("--venue", default="local-hardware")
    parser.add_argument("--flow", default="live")
    parser.add_argument("--run-dir", default="", help="Workspace/run directory.")
    parser.add_argument("--department", default="core")
    return parser.parse_args()


def _build_epic(task: dict, task_context_file: str, output_file: str) -> dict:
    task_id = str(task.get("id", "unknown"))
    instruction = str(task.get("instruction", "")).strip()
    description = str(task.get("description", "")).strip()
    acceptance = task.get("acceptance_contract", {})
    pass_conditions = acceptance.get("pass_conditions", [])
    pass_text = "; ".join(str(item) for item in pass_conditions if str(item).strip()) or "Task-level checks pass."

    return {
        "name": "",
        "description": f"Live benchmark task {task_id}",
        "status": "ready",
        "team": "standard",
        "environment": "standard",
        "issues": [
            {
                "id": f"LB-{task_id}-1",
                "summary": f"Execute benchmark task {task_id}",
                "seat": "coder",
                "status": "ready",
                "priority": "High",
                "note": (
                    f"Read {task_context_file}. Then write {output_file}. "
                    "The output must include task id, summary, implementation plan, and acceptance checks. "
                    "If any file is missing, create it instead of failing. "
                    f"Description: {description} "
                    f"Instruction: {instruction or 'No explicit instruction provided; use description and acceptance contract.'} "
                    f"Pass conditions: {pass_text}"
                ),
            }
        ],
    }


def main() -> int:
    args = _parse_args()
    task_path = Path(args.task)
    task = json.loads(task_path.read_text(encoding="utf-8"))
    task_id = str(task.get("id", "unknown"))

    run_dir = Path(args.run_dir) if args.run_dir else task_path.parent
    run_dir.mkdir(parents=True, exist_ok=True)
    task_context_path = run_dir / "task_context.json"
    output_file = f"benchmark_task_{task_id}_output.md"
    task_context_path.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")

    epic_name = f"benchmark_live_{task_id}_{uuid.uuid4().hex[:8]}"
    epic_path = Path("model") / str(args.department) / "epics" / f"{epic_name}.json"
    epic_payload = _build_epic(
        task=task,
        task_context_file=task_context_path.name,
        output_file=output_file,
    )
    epic_payload["name"] = epic_name

    epic_path.parent.mkdir(parents=True, exist_ok=True)
    epic_path.write_text(json.dumps(epic_payload, indent=2) + "\n", encoding="utf-8")

    cmd = [
        "python",
        "main.py",
        "--epic",
        epic_name,
        "--department",
        str(args.department),
        "--workspace",
        str(run_dir),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    finally:
        try:
            epic_path.unlink(missing_ok=True)
        except OSError:
            pass

    # Persist command output as an artifact for harness hashing and troubleshooting.
    (run_dir / "live_runner_output.log").write_text(
        ((result.stdout or "") + "\n" + (result.stderr or "")).strip() + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "task_id": task_id,
                "exit_code": int(result.returncode),
                "workspace": str(run_dir).replace("\\", "/"),
                "output_file": output_file,
            },
            sort_keys=True,
        )
    )
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
