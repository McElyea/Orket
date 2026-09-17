"""Layer: contract. Receipt timing cannot claim contradictory provenance."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from orket.core.contracts.protocol_receipt_timing import ProtocolReceiptTiming, protocol_receipt_timing

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("duration,provenance", [
    (None, {"status": "reported", "source": "runtime_context", "reason": None}),
    (0.0, {"status": "reported", "source": None, "reason": None}),
    (0.0, {"status": "reported", "source": "runtime_context", "reason": "missing"}),
    (0.0, {"status": "unavailable", "source": None, "reason": "missing"}),
    (None, {"status": "unavailable", "source": "runtime_context", "reason": "missing"}),
    (None, {"status": "unavailable", "source": None, "reason": None}),
    (True, {"status": "reported", "source": "runtime_context", "reason": None}),
    (float("inf"), {"status": "reported", "source": "runtime_context", "reason": None}),
])
# Layer: contract
def test_receipt_timing_rejects_contradictory_provenance(duration, provenance):
    """Layer: contract. Contradictory status, source and value cannot serialize."""
    with pytest.raises(ValidationError):
        ProtocolReceiptTiming(validator_duration_ms=duration, validator_timing=provenance)


# Layer: contract
def test_receipt_timing_wire_roundtrip_retains_unavailable_and_fractional_values():
    """Layer: contract. Valid nullable and fractional fields round-trip exactly."""
    for value in (None, 0, 0.25, 17):
        timing = protocol_receipt_timing(value)
        assert ProtocolReceiptTiming.model_validate_json(timing.model_dump_json()) == timing
