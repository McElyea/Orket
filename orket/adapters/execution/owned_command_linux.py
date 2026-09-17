"""Linux subreaper backend, used only by the dedicated supervisor subprocess."""
from __future__ import annotations

import ctypes
import os
import signal
from pathlib import Path

side_effecting = True


class LinuxChildren:
    def __init__(self):
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
            raise OSError(ctypes.get_errno(), "Cannot establish verification subreaper")
        self.children_path = Path(f"/proc/{os.getpid()}/task/{os.getpid()}/children")
        self.children_path.read_text(encoding="ascii")  # Refuse before dispatch if inventory is unavailable.

    def reap(self, process):
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return True
            if pid == 0:
                return False
            if process is not None and pid == process.pid:
                process.returncode = os.waitstatus_to_exitcode(status)

    def stop(self, *, force):
        # Reaping and signalling run on this one thread. A direct child cannot have
        # its PID reused until this subreaper waits on it. Killing a parent adopts
        # its children here, including descendants that changed session/group.
        for token in self.children_path.read_text(encoding="ascii").split():
            try:
                os.kill(int(token), signal.SIGKILL if force else signal.SIGTERM)
            except ProcessLookupError:
                continue  # The next waitpid, not this signal result, establishes exit.
