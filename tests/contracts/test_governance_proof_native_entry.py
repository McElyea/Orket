"""Layer: contract. Governance synchronous commands refuse before process mutation."""

import os

import pytest

from scripts.governance.record_truthful_runtime_artifact_provenance_live_proof import (
    record_truthful_runtime_artifact_provenance_live_proof,
)
from scripts.governance.record_truthful_runtime_packet1_live_proof import record_truthful_runtime_packet1_live_proof
from scripts.governance.record_truthful_runtime_packet2_repair_live_proof import (
    record_truthful_runtime_packet2_repair_live_proof,
)

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


@pytest.mark.parametrize(
    "command",
    [
        record_truthful_runtime_packet1_live_proof,
        record_truthful_runtime_packet2_repair_live_proof,
        record_truthful_runtime_artifact_provenance_live_proof,
    ],
)
async def test_governance_proof_refuses_active_loop_before_environment_mutation(command):
    before = dict(os.environ)
    try:
        with pytest.raises(RuntimeError, match="E_GOVERNANCE_PROOF_REQUIRES_NATIVE_CONTEXT"):
            command(model="unadmitted-fixture", provider="openai_compat", epic_id="refused")
        assert dict(os.environ) == before
    finally:
        # The old packet1 finally block can fail before restoring its overrides.
        os.environ.clear()
        os.environ.update(before)
