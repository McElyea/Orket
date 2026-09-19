from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.application.test_prompts_cli import _command

pytestmark = pytest.mark.integration


def test_canonical_prompt_resolution_from_repo_assets(tmp_path: Path) -> None:
    shutil.copytree(Path('model'), tmp_path / 'model')
    resolved = _command(
        tmp_path, "resolve",
        role="architect",
        dialect="generic",
        selection_policy="stable",
        strict=True,
    )
    metadata = resolved["metadata"]
    layers = resolved["layers"]

    assert metadata["prompt_id"] == "role.architect+dialect.generic"
    assert metadata["selection_policy"] == "stable"
    assert metadata["role_status"] in {"stable", "candidate", "canary"}
    assert metadata["dialect_status"] in {"stable", "candidate", "canary"}
    assert layers["role_base"]["name"] == "architect"
    assert layers["dialect_adapter"]["name"] == "generic"
