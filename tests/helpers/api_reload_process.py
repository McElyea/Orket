"""Synchronous integration-test process ownership for private server consoles/groups."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import psutil

CONSOLE_SIGNAL = """
import ctypes, sys, psutil
pid, created, script = int(sys.argv[1]), float(sys.argv[2]), sys.argv[3]
process = psutil.Process(pid)
assert process.create_time() == created and script in process.cmdline()
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.FreeConsole()
assert kernel.AttachConsole(pid), ctypes.get_last_error()
assert kernel.SetConsoleCtrlHandler(None, True), ctypes.get_last_error()
assert kernel.GenerateConsoleCtrlEvent(0, 0), ctypes.get_last_error()
"""


def until(observation, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = observation()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError(f"Server observation did not settle within {timeout} seconds")


def signal_server(process, script):
    if process.poll() is not None:
        return
    if os.name == "nt":
        owner = psutil.Process(process.pid)
        result = subprocess.run(
            [sys.executable, "-c", CONSOLE_SIGNAL, str(owner.pid), str(owner.create_time()), str(script)],
            capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        os.killpg(process.pid, signal.SIGINT)


def _launch(command, project, environment, log):
    job = None
    kwargs = {"start_new_session": True}
    if os.name == "nt":
        from orket.adapters.execution.owned_command_windows import WindowsJob

        job = WindowsJob()
        startup = subprocess.STARTUPINFO()
        startup.dwFlags = subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
        kwargs = {"creationflags": subprocess.CREATE_NEW_CONSOLE | 0x00000004, "startupinfo": startup}
    process = subprocess.Popen(command, cwd=project, env=environment, stdout=log, stderr=subprocess.STDOUT, **kwargs)
    if job is not None:
        try:
            job.admit(process)
            job.release(process)
        except OSError:
            process.kill()
            process.wait(timeout=10)
            job.close()
            raise
    return process, job


def _finish(process, job, script):
    forced = False
    try:
        if process.poll() is None:
            signal_server(process, script)
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            forced = True
            if job is not None:
                job.stop()
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)
        if job is not None:
            deadline = time.monotonic() + 5
            while not job.empty() and time.monotonic() < deadline:
                time.sleep(0.05)
            if not job.empty():
                forced = True
                job.stop()
            until(job.empty, timeout=5)
        else:
            deadline = time.monotonic() + 5
            while not _group_empty(process.pid) and time.monotonic() < deadline:
                time.sleep(0.05)
            if not _group_empty(process.pid):
                forced = True
                os.killpg(process.pid, signal.SIGKILL)
            until(lambda: _group_empty(process.pid), timeout=5)
        assert not forced, "Server required forced cleanup; inspect server.log"
    finally:
        if job is not None:
            job.close()


def _group_empty(pid):
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return True
    return False


@contextmanager
def owned_server(project: Path, arguments: list[str], environment: dict[str, str]):
    script = project / "server.py"
    with (project / "server.log").open("wb") as log:
        process, job = _launch([sys.executable, str(script), *arguments], project, environment, log)
        try:
            yield process
        finally:
            _finish(process, job, script)
