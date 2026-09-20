"""Real local review and trusted extension fixtures for terminal conformance."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiosqlite

from orket.application.review.models import SnapshotBounds
from orket.application.review.run_service import ReviewRunService
from orket.application.services.extension_catalog_commands import prepare_extension_manager
from orket.application.services.extension_workload_composition import prepare_extension_workload_control_plane_service
from orket.application.services.review_run_control_plane_service import build_review_run_control_plane_service
from orket.core.domain import AuthoritySourceClass, ResultClass
from tests.application.test_review_run_service import _git, _init_repo
from tests.runtime.test_extension_manager import _init_sdk_extension_repo, _init_test_extension_repo


def database_for(family: str, folder: Path) -> Path:
    return folder / ("control_plane.sqlite3" if family == "review" else ".orket/durable/db/control_plane_records.sqlite3")


def review_flow(folder: Path):
    repo = folder / "review-source"
    _init_repo(repo)
    (repo / "sample.py").write_text("print('review fixture')\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "review fixture")
    service = ReviewRunService(workspace=folder / "workspace", control_plane_db_path=database_for("review", folder))
    return service.run_files(repo_root=repo, ref="HEAD", paths=["sample.py"], bounds=SnapshotBounds())


async def run_family(family: str, folder: Path):
    if family == "review":
        return await asyncio.to_thread(review_flow, folder)
    repo = folder / "extension-source"
    await asyncio.to_thread(repo.mkdir, parents=True)
    await asyncio.to_thread(_init_sdk_extension_repo if family == "sdk" else _init_test_extension_repo, repo)
    manager = await prepare_extension_manager(catalog_path=folder / "extensions_catalog.json", project_root=folder)
    await manager.install_from_repo(str(repo))
    return await manager.run_workload(
        workload_id="sdk_v1" if family == "sdk" else "mystery_v1",
        input_config={"seed": 321, "mode": "basic"}, workspace=folder / "workspace/default", department="core",
    )


async def records(db: Path) -> dict[str, list[dict]]:
    async with aiosqlite.connect(db.as_uri() + "?mode=ro", uri=True) as connection:
        result = {}
        for table in ("control_plane_runs", "control_plane_attempts", "control_plane_steps",
                      "effect_journal_entries", "final_truth_records"):
            cursor = await connection.execute("SELECT payload_json FROM " + table)
            result[table] = [json.loads(row[0]) for row in await cursor.fetchall()]
        return result


async def retained_request(family: str, folder: Path):
    rows = await records(database_for(family, folder))
    run = rows["control_plane_runs"][0]
    if family == "review":
        return build_review_run_control_plane_service(database_for(family, folder)), {"run_id": run["run_id"]}
    truth = rows["final_truth_records"][0]
    step = next(row for row in rows["control_plane_steps"] if row["step_kind"].endswith("closeout"))
    owner = await prepare_extension_workload_control_plane_service(project_root=folder)
    return owner, dict(run_id=run["run_id"], outcome=ResultClass(truth["result_class"]),
        authoritative_result_ref=truth["authoritative_result_ref"], prior_step_ref=step["input_ref"],
        authority_sources=[AuthoritySourceClass(value) for value in truth["authority_sources"]])


async def repeat_closeout(family, owner, request):
    if family == "review":
        return await owner.finalize_completed(**request)
    return await owner.finalize_execution(**request)
