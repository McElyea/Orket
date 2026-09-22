"""Layer: contract. Only exact approved identity authorizes approval-required work."""

from dataclasses import FrozenInstanceError, replace

import pytest

from orket.core.contracts.kernel_authorization import ApprovalIdentity, admission_authorization_refusal

pytestmark = pytest.mark.contract
IDENTITY = ApprovalIdentity("session", "proposal", "decision")


@pytest.mark.parametrize(
    "decision,status,observed,expected",
    [
        ("ACCEPT_TO_UNIFY", "", None, ""),
        ("NEEDS_APPROVAL", "APPROVED", IDENTITY, ""),
        ("REJECT", "APPROVED", IDENTITY, "REJECTED_POLICY"),
        ("UNKNOWN", "APPROVED", IDENTITY, "REJECTED_POLICY"),
        ("", "APPROVED", IDENTITY, "REJECTED_POLICY"),
        *[
            ("NEEDS_APPROVAL", status, IDENTITY, "REJECTED_APPROVAL_MISSING")
            for status in ("", "PENDING", "DENIED", "APPROVED_WITH_EDITS", "EXPIRED")
        ],
        ("NEEDS_APPROVAL", "APPROVED", None, "REJECTED_APPROVAL_MISSING"),
        *[
            ("NEEDS_APPROVAL", "APPROVED", replace(IDENTITY, **{field: "foreign"}), "REJECTED_APPROVAL_MISSING")
            for field in ("session_id", "proposal_digest", "decision_digest")
        ],
    ],
)
def test_authorization_truth_table(decision, status, observed, expected):
    assert (
        admission_authorization_refusal(decision=decision, expected=IDENTITY, approval_status=status, observed=observed)
        == expected
    )


def test_identity_is_immutable_and_rejects_mutable_values():
    with pytest.raises(FrozenInstanceError):
        IDENTITY.session_id = "changed"
    with pytest.raises(ValueError, match="E_APPROVAL_IDENTITY_INVALID"):
        ApprovalIdentity([], "proposal", "decision")
