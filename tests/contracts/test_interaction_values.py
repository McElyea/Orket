"""Explicit interaction identity and immutable commit input contracts."""
from pathlib import Path

import pytest
from pydantic import ValidationError

from orket.adapters.storage.interaction_artifact_store import InteractionArtifactStore
from orket.core.contracts.interaction_stream import CommitIntent, validate_interaction_id

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("identity", ["", ".", "..", "../outside", "a/b", "a\\b", "C:drive", "a" * 129])
def test_path_like_or_unbounded_identity_is_refused(identity):
    with pytest.raises(ValueError, match="E_INTERACTION_ID_INVALID"):
        validate_interaction_id(identity)


def test_commit_intent_cannot_be_retargeted_after_admission():
    intent = CommitIntent(type="decision", ref="original")
    with pytest.raises(ValidationError, match="frozen"):
        intent.ref = "changed"
    assert intent.ref == "original"


def test_artifact_root_must_be_explicit_and_absolute():
    with pytest.raises(ValueError, match="E_INTERACTION_ROOT_ABSOLUTE_REQUIRED"):
        InteractionArtifactStore(Path("relative"))
