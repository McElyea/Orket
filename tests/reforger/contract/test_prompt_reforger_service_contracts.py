from __future__ import annotations

import pytest

from orket.reforger.proof_slices import phase0_adapt_request, phase0_baseline_request
from orket.reforger.service_contracts import (
    PromptReforgerServiceRequest,
    SERVICE_MODE_ADAPT,
)


@pytest.mark.contract
def test_bounded_adapt_requires_candidate_budget() -> None:
    payload = phase0_adapt_request().to_payload()
    payload.pop("candidate_budget", None)

    with pytest.raises(ValueError, match="candidate_budget is required"):
        PromptReforgerServiceRequest.from_payload(payload)


@pytest.mark.contract
def test_phase0_request_roundtrip_preserves_contract_fields() -> None:
    baseline = PromptReforgerServiceRequest.from_payload(phase0_baseline_request().to_payload())
    adapt = PromptReforgerServiceRequest.from_payload(phase0_adapt_request().to_payload())

    assert baseline.to_payload() == phase0_baseline_request().to_payload()
    assert adapt.to_payload() == phase0_adapt_request().to_payload()
    assert adapt.service_mode == SERVICE_MODE_ADAPT
    assert adapt.candidate_budget == 4
