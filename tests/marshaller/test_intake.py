from orket.marshaller.intake import (
    BINARY_DELTA_DENIED,
    FORBIDDEN_PATH,
    PATCH_TOO_LARGE,
    RENAME_CAP_EXCEEDED,
    SCHEMA_INVALID,
    SECRETS_DETECTED,
    evaluate_patch_proposal,
    validate_patch_proposal_payload,
)


def _base_payload() -> dict:
    return {
        "proposal_id": "p-001",
        "proposal_contract_version": "v0",
        "base_revision_digest": "sha256:abc",
        "patch": "diff --git a/orket/foo.py b/orket/foo.py\n+print('ok')\n",
        "intent": "Add log statement",
        "touched_paths": ["orket/foo.py"],
        "rationale": "Needed for observability",
    }


def test_validate_patch_proposal_payload_accepts_valid_schema() -> None:
    result = validate_patch_proposal_payload(_base_payload())
    assert result.ok is True
    assert result.rejection_codes == ()
    assert result.proposal is not None


def test_validate_patch_proposal_payload_rejects_invalid_schema() -> None:
    payload = _base_payload()
    payload.pop("proposal_id")
    result = validate_patch_proposal_payload(payload)
    assert result.ok is False
    assert result.rejection_codes == (SCHEMA_INVALID,)
    assert result.primary_rejection_code == SCHEMA_INVALID
    assert result.errors


def test_evaluate_patch_proposal_rejects_forbidden_paths() -> None:
    payload = _base_payload()
    payload["touched_paths"] = ["../secrets.txt"]
    result = evaluate_patch_proposal(payload, allowed_paths=("orket",))
    assert result.ok is False
    assert result.rejection_codes == (FORBIDDEN_PATH,)


def test_evaluate_patch_proposal_rejects_safety_violations_in_order() -> None:
    payload = _base_payload()
    payload["patch"] = (
        "diff --git a/orket/foo.py b/orket/foo.py\n"
        "rename from a.py\n"
        "rename from b.py\n"
        "AKIA1234567890ABCDEF\n"
        "GIT binary patch\n"
        + ("x" * 64)
    )
    result = evaluate_patch_proposal(
        payload,
        allowed_paths=("orket",),
        max_patch_bytes=10,
        rename_cap=1,
    )
    assert result.ok is False
    assert result.rejection_codes == (
        PATCH_TOO_LARGE,
        SECRETS_DETECTED,
        BINARY_DELTA_DENIED,
        RENAME_CAP_EXCEEDED,
    )
    assert result.primary_rejection_code == PATCH_TOO_LARGE


def test_evaluate_patch_proposal_refactor_mode_skips_rename_cap() -> None:
    payload = _base_payload()
    payload["patch"] = (
        "diff --git a/orket/foo.py b/orket/foo.py\n"
        "rename from a.py\n"
        "rename from b.py\n"
    )
    result = evaluate_patch_proposal(
        payload,
        allowed_paths=("orket",),
        rename_cap=1,
        refactor_mode=True,
    )
    assert result.ok is True
