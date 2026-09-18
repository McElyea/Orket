"""Fail closed on stray worktree-root SQLite access in proof subprocesses."""
import os
import sys
from pathlib import Path


def pytest_configure(config):
    protected = Path.cwd().resolve() / "control_plane_records.sqlite3"
    config._root_database_guard_events = []

    def audit(event, args):
        if event not in {"sqlite3.connect", "os.remove"} or not args:
            return
        if event == "os.remove" and len(args) > 1 and args[1] != -1:
            return  # Relative dir-fd deletion belongs to that directory, not the worktree root.
        value = args[0]
        if not isinstance(value, (str, bytes, os.PathLike)):
            return
        decoded = os.fsdecode(value)
        if decoded == ":memory:":
            return
        if Path(decoded).resolve() == protected:
            config._root_database_guard_events.append(event)
            raise RuntimeError(f"Proof attempted {event} on worktree-root database: {protected}")

    sys.addaudithook(audit)


def pytest_sessionfinish(session, exitstatus):
    events = session.config._root_database_guard_events
    if events:
        session.exitstatus = 1
        reporter = session.config.pluginmanager.getplugin("terminalreporter")
        if reporter is not None:
            reporter.write_sep("!", "Worktree-root database guard rejected: " + ", ".join(events))
