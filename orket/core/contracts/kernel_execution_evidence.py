"""Pure classification of claimed and observed Kernel execution evidence."""


def execution_evidence_status(*, execution_claimed: bool, executed: bool, validated: bool) -> str:
    if executed and validated:
        return "validated_execution"
    if executed:
        return "execution_observed_only"
    if execution_claimed and validated:
        return "claimed_result_validated_only"
    if execution_claimed:
        return "claimed_only"
    if validated:
        return "result_validated_without_execution_claim"
    return "absent"
