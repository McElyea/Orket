"""Layer: contract. Simulated alias responses prove ownership and environment restoration only."""

import os

import pytest

from scripts.governance import record_truthful_runtime_packet1_live_proof as packet1

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("mode", ["existing", "created", "create-failure", "remove-failure", "missing-cli"])
def test_packet1_restores_environment_and_only_removes_owned_alias(tmp_path, monkeypatch, mode):
    calls = []
    monkeypatch.chdir(tmp_path)
    before = dict(os.environ)

    async def command(*args):
        calls.append(args)
        if mode == "missing-cli":
            raise FileNotFoundError("controlled missing ollama executable")
        if args[1] == "show":
            return (0 if mode == "existing" else 1), "", ""
        if args[1] == "cp":
            return (1 if mode == "create-failure" else 0), "", "controlled copy outcome"
        assert args[1] == "rm"
        return (1 if mode == "remove-failure" else 0), "", "controlled removal outcome"

    async def execute(**options):
        assert options["workspace"].is_dir()
        raise ValueError("controlled proof refusal")

    monkeypatch.setattr(packet1, "_run_command", command)
    monkeypatch.setattr(packet1, "_execute_live_proof", execute)
    expected = {
        "missing-cli": FileNotFoundError,
        "create-failure": AssertionError,
        "remove-failure": AssertionError,
    }.get(mode, ValueError)
    try:
        with pytest.raises(expected):
            packet1.record_truthful_runtime_packet1_live_proof(model="qwen2.5:7b", provider="ollama", epic_id="fixture")
        assert dict(os.environ) == before
        verbs = [args[1] for args in calls]
        expected_verbs = (
            ["show"]
            if mode in {"existing", "missing-cli"}
            else ["show", "cp"]
            if mode == "create-failure"
            else ["show", "cp", "rm"]
        )
        assert verbs == expected_verbs
    finally:
        os.environ.clear()
        os.environ.update(before)
