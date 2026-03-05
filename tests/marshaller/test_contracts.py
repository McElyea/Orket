import pytest
from pydantic import ValidationError

from orket.marshaller.contracts import RunRequest


def _base_run_request_payload() -> dict:
    return {
        "repo_path": "C:/Source/Orket",
        "task_spec": {"goal": "stabilize"},
        "checks": ["build", "test"],
        "seed": 7,
        "max_attempts": 2,
        "execution_envelope": {
            "mode": "lockfile",
            "lockfile_digest": "sha256:abc123",
        },
    }


def test_run_request_defaults_model_streams_to_one() -> None:
    model = RunRequest.model_validate(_base_run_request_payload())
    assert model.model_streams == 1


def test_lockfile_mode_requires_lockfile_digest() -> None:
    payload = _base_run_request_payload()
    payload["execution_envelope"] = {"mode": "lockfile"}
    with pytest.raises(ValidationError):
        RunRequest.model_validate(payload)


def test_container_mode_requires_container_image_digest() -> None:
    payload = _base_run_request_payload()
    payload["execution_envelope"] = {"mode": "container"}
    with pytest.raises(ValidationError):
        RunRequest.model_validate(payload)


def test_container_mode_accepts_container_image_digest() -> None:
    payload = _base_run_request_payload()
    payload["execution_envelope"] = {
        "mode": "container",
        "container_image_digest": "sha256:deadcafe",
    }
    model = RunRequest.model_validate(payload)
    assert model.execution_envelope.mode == "container"
