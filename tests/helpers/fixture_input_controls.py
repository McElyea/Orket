"""Fixture-input controls: real files and bounded native fault holds."""
from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from orket.schema import IssueVerification, VerificationScenario

NOW = datetime(2042, 6, 15, 12, tzinfo=UTC)
SOURCE = """import json, os
from pathlib import Path
def verify(data):
    Path('observed.json').write_text(json.dumps({'input': data, 'cwd': os.getcwd(),
        'policy': os.environ.get('FIXTURE_CAPTURE_VALUE')}))
    return data['nested']['value']
"""


def selected_time():
    return NOW


def prepare_native(root, source=SOURCE):
    directory = root / "verification"
    directory.mkdir(parents=True)
    (directory / "fixture.py").write_text(source, encoding="utf-8")
    return IssueVerification(fixture_path="verification/fixture.py", scenarios=[
        VerificationScenario(id="S1", description="original scenario",
                             input_data={"nested": {"value": 7}}, expected_output=7)])


def observation(root):
    return json.loads((root / "verification/observed.json").read_text(encoding="utf-8"))


def fail_metadata(monkeypatch, selected, failure):
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(),
                            finished=threading.Event(), expired=False, thread=None)
    original = Path.is_file

    def held(path):
        if path != selected or state.entered.is_set():
            return original(path)
        state.thread = threading.get_ident()
        state.entered.set()
        try:
            state.expired = not state.release.wait(5)
            assert not state.expired, "fixture metadata release missing"
            original(path)  # Perform the actual metadata observation before refusal.
            raise failure
        finally:
            state.finished.set()

    monkeypatch.setattr(Path, "is_file", held)
    return state


class HookedDict(dict):
    def __init__(self):
        super().__init__(value="original")
        self.calls = []

    def __deepcopy__(self, memo):
        self.calls.append("deepcopy")
        threading.Event().wait(1)  # Bounded adverse hook; must never be invoked.
        return self

    def items(self):
        self.calls.append("items")
        threading.Event().wait(1)
        return super().items()
