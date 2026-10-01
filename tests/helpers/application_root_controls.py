"""Finite native holds and real matching trees for isolated root-input controls."""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import threading
from pathlib import Path

import psutil

import orket
from orket.adapters.execution import owned_io
from tests.helpers.core_effect_fixtures import BOARD_ASSETS


class NativeHold:
    def __init__(self):
        self.entered, self.release, self.finished = threading.Event(), threading.Event(), threading.Event()
        self.calls, self.worker, self.expired = 0, None, False

    def wait(self):
        self.calls += 1
        self.worker = threading.get_ident()
        self.entered.set()
        self.expired = not self.release.wait(10)
        assert not self.expired, "root-input native hold was not released"


def prepare_trees(root):
    first, other = root / "first", root / "other"
    for project in (first, other):
        (project / "workspace/default").mkdir(parents=True)
        for asset in BOARD_ASSETS:
            target = project / "model" / asset.relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(asset.content, encoding="utf-8")
    return first, other


def contents(project):
    return {asset.relative_path: (project / "model" / asset.relative_path).read_text(encoding="utf-8")
            for asset in BOARD_ASSETS}


def records(project):
    path = project / "workspace/default/orket.log"
    return [json.loads(line) for line in path.read_bytes().splitlines()] if path.exists() else []


async def admitted(hold, active):
    assert await asyncio.to_thread(hold.entered.wait, 3), "native root-input operation did not start"
    assert hold.worker != threading.get_ident() and not active.done()


async def settle(active, hold):
    hold.release.set()
    await asyncio.wait_for(asyncio.gather(active, return_exceptions=True), 10)


def origins(modules):
    process = psutil.Process()
    return {"interpreter": sys.executable, "prefix": sys.prefix, "origin": str(Path(orket.__file__).resolve()),
        "owner_origin": str(Path(owned_io.__file__).resolve()),
        "owner_sha256": hashlib.sha256(Path(owned_io.__file__).read_bytes()).hexdigest(),
        "process_identity": {"pid": process.pid, "create_time": process.create_time()},
        "sources": {name: {"path": str(Path(module.__file__).resolve()),
                            "sha256": hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()}
                    for name, module in modules.items()}}
