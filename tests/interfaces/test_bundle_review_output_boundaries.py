"""Contract: real CLI parsing/printing with a supplied review service and failing output sink."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.application.review.bundle_validation import ReviewBundleError
from orket.application.review.run_service import ReviewRunService
from orket.interfaces.orket_bundle_cli import main

pytestmark = pytest.mark.contract


class FailingOutput(io.StringIO):
    def __init__(self, failure):
        super().__init__()
        self.failure = failure
        self.attempts = []

    def write(self, value):
        self.attempts.append(value)
        if self.failure is not None:
            failure, self.failure = self.failure, None
            raise failure
        return super().write(value)


def review_arguments(tmp_path, phase, emit_json):
    command = ["review", "replay"] if phase == "replay_missing" else ["review", "diff", "--base", "a", "--head", "b"]
    command += ["--workspace", str(tmp_path / "workspace"), "--repo-root", str(tmp_path)]
    if phase == "scope":
        command += ["--code-only", "--all-files"]
    if emit_json:
        command += ["--json"]
    return command


@pytest.mark.parametrize("phase", ["replay_missing", "scope", "bundle_error", "ordinary_error", "success"])
@pytest.mark.parametrize("emit_json", [False, True])
def test_review_output_failure_keeps_its_original_catch_boundary(tmp_path, monkeypatch, phase, emit_json):
    constructed, executed = [], []
    failure = OSError("controlled CLI output failure")
    output = FailingOutput(failure)
    monkeypatch.setattr(ReviewRunService, "__init__", lambda self, *, workspace: constructed.append(workspace))

    def run_diff(_self, **_kwargs):
        executed.append("diff")
        if phase == "bundle_error":
            raise ReviewBundleError(error_code="E_FIXTURE_REVIEW_BUNDLE", field="fixture.field")
        if phase == "ordinary_error":
            raise ValueError("controlled review execution failure")
        return SimpleNamespace(to_dict=lambda: {"ok": True, "exit_code": 0})

    monkeypatch.setattr(ReviewRunService, "run_diff", run_diff)
    monkeypatch.setattr(sys, "stdout", output)
    arguments = review_arguments(tmp_path, phase, emit_json)
    if phase == "replay_missing":
        assert main(arguments) == 1
        if emit_json:
            result = json.loads(output.getvalue())
            assert result == {"ok": False, "error_count": 1, "errors": [{"code": "E_REVIEW_RUN_FAILED",
                "location": "review.replay", "message": str(failure)}], "exit_code": 1}
        else:
            assert output.getvalue() == "FAIL (1 error(s))\n[E_REVIEW_RUN_FAILED] review.replay: controlled CLI output failure\n"
    else:
        with pytest.raises(OSError) as raised:
            main(arguments)
        assert raised.value is failure and output.getvalue() == ""
    assert bool(constructed) is (phase != "scope")
    assert executed == ([] if phase in {"scope", "replay_missing"} else ["diff"])
    assert len(output.attempts) == (3 if phase == "replay_missing" else 1)


@pytest.mark.parametrize("stage", ["policy", "workspace", "service"])
def test_review_preparation_failure_stays_outside_execution_envelope(tmp_path, monkeypatch, capsys, stage):
    failure = OSError("controlled review preparation failure")
    observed = []
    policy, workspace = tmp_path / "policy.json", tmp_path / "workspace"
    original = Path.resolve

    def resolve(path, *args, **kwargs):
        if path == {"policy": policy, "workspace": workspace}.get(stage):
            observed.append(stage)
            raise failure
        return original(path, *args, **kwargs)

    def initialize(_self, *, workspace):
        observed.append("service")
        raise failure

    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setattr(ReviewRunService, "__init__", initialize)
    with pytest.raises(OSError) as raised:
        main(["review", "diff", "--base", "a", "--head", "b", "--policy", str(policy),
              "--workspace", str(workspace), "--json"])
    assert raised.value is failure and observed == [stage] and capsys.readouterr().out == ""
