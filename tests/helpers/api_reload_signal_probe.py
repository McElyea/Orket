"""Native integration probe: real reload handlers under owned event conditions."""
from __future__ import annotations

import argparse
import faulthandler
import hashlib
import json
import multiprocessing
import os
import signal
from contextlib import nullcontext
from pathlib import Path

import uvicorn

import orket
from orket.interfaces import api_reload_runtime


def deliver_signals(owner, event, held):
    previous = signal.signal(signal.SIGINT, owner)
    try:
        # The real Event uses a non-reentrant condition in both native owners.
        with event._cond if held else nullcontext():
            signal.raise_signal(signal.SIGINT)
            signal.raise_signal(signal.SIGINT)
        return previous
    except BaseException:
        signal.signal(signal.SIGINT, previous)
        raise


def parent_probe(config, server, stop, held):
    parent = api_reload_runtime._ReloadSupervisor(config, server, [], stop)
    previous = deliver_signals(parent.signal_handler, parent.should_exit, held)
    try:
        try:
            parent.pause()
        except StopIteration:
            assert parent.should_exit.is_set()
            return ["signals_returned", "pause_stopped", "watcher_stop_published"]
        raise AssertionError("Actual reload pause did not stop after the signals")
    finally:
        signal.signal(signal.SIGINT, previous)


def worker_probe(config, server, stop, held, lifecycle):
    previous = deliver_signals(server.handle_exit, stop, held)
    listener = config.bind_socket()
    try:
        # Signal admission precedes startup; run the actual loop and ASGI lifecycle.
        server.run(sockets=[listener])
        assert lifecycle == ["startup", "shutdown"]
        assert server.started and server.should_exit and not server.force_exit
        return ["signals_returned", "lifespan_startup", "lifespan_shutdown", "serve_returned"]
    finally:
        listener.close()
        signal.signal(signal.SIGINT, previous)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", choices=("parent", "worker"), required=True)
    parser.add_argument("--condition", choices=("held", "free"), required=True)
    args = parser.parse_args()
    lifecycle = []

    async def application(scope, receive, send):
        assert scope["type"] == "lifespan"
        assert (await receive())["type"] == "lifespan.startup"
        lifecycle.append("startup")
        await send({"type": "lifespan.startup.complete"})
        assert (await receive())["type"] == "lifespan.shutdown"
        lifecycle.append("shutdown")
        await send({"type": "lifespan.shutdown.complete"})

    config = uvicorn.Config(application, host="127.0.0.1", port=0, lifespan="on",
                            reload=args.owner == "parent", log_level="warning")
    stop = multiprocessing.get_context("spawn").Event()
    server = api_reload_runtime._ReloadServer(config, stop)
    held = args.condition == "held"
    module = Path(api_reload_runtime.__file__).resolve()
    root = Path(orket.__file__).resolve().parent
    assert module.is_relative_to(root)
    faulthandler.enable()
    faulthandler.dump_traceback_later(2)
    try:
        states = (parent_probe(config, server, stop, held) if args.owner == "parent"
                  else worker_probe(config, server, stop, held, lifecycle))
        print(json.dumps({"observed_path": "primary", "observed_result": "success",
                          "owner": args.owner, "condition": args.condition, "pid": os.getpid(),
                          "signals_delivered": 2, "completed_states": states,
                          "module_origin": str(module),
                          "module_sha256": hashlib.sha256(module.read_bytes()).hexdigest()}), flush=True)
    finally:
        faulthandler.cancel_dump_traceback_later()


if __name__ == "__main__":
    main()
