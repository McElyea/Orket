from __future__ import annotations

from pathlib import Path


def test_core_release_policy_handles_zero_push_base_sha() -> None:
    """Layer: contract. Verifies direct-push commit policy has a bounded first-push base fallback."""
    workflow_text = Path(".gitea/workflows/core-release-policy.yml").read_text(encoding="utf-8")

    assert 'BASE_SHA="${{ github.event.before }}"' in workflow_text
    assert 'if [ "$BASE_SHA" = "0000000000000000000000000000000000000000" ]; then' in workflow_text
    assert "BASE_SHA=$(git rev-list --max-parents=0 HEAD)" in workflow_text
    assert "EXTRA_ARGS+=(--require-commit-tags)" in workflow_text
