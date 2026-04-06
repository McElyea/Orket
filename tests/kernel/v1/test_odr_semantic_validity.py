from __future__ import annotations

import pytest

from orket.kernel.v1.odr.semantic_validity import (
    _contradiction_hits,
    _matches_any,
    _matches_authorized_removal,
    _tokens,
    _unresolved_alternative_hits,
    classify_patch_classes,
    evaluate_semantic_validity,
)

pytestmark = pytest.mark.unit


def test_contradiction_hits_must_not_alone_does_not_fire() -> None:
    text = "The system must not store data outside the jurisdiction."
    assert _contradiction_hits(text) == []


def test_contradiction_hits_disallow_alone_does_not_fire() -> None:
    text = "The system must disallow outbound connections."
    assert _contradiction_hits(text) == []


def test_contradiction_hits_genuine_retain_delete_fires() -> None:
    text = "The system must retain user data. The system must delete user data after 30 days."
    hits = _contradiction_hits(text)
    assert "retain|delete" in hits


def test_contradiction_hits_must_plus_must_not_different_subjects_does_not_fire() -> None:
    text = "The system must encrypt data. The system must not store PII externally."
    assert _contradiction_hits(text) == []


def test_contradiction_hits_should_plus_should_not_does_not_fire() -> None:
    text = "Logs should be rotated weekly. Logs should not be deleted before audit."
    assert _contradiction_hits(text) == []


def test_contradiction_hits_store_locally_upload_fires() -> None:
    text = "Must store profile data locally only. Must upload profile data to remote."
    hits = _contradiction_hits(text)
    assert "store locally|upload" in hits


def test_contradiction_hits_empty_text_returns_empty() -> None:
    assert _contradiction_hits("") == []


def test_unresolved_or_in_constraint_does_not_fire() -> None:
    assert _unresolved_alternative_hits("The system must encrypt or hash all stored passwords.") == []


def test_unresolved_may_does_not_fire() -> None:
    assert _unresolved_alternative_hits("The cache layer may store results for up to 10 seconds.") == []


def test_unresolved_either_or_fires() -> None:
    hits = _unresolved_alternative_hits("The system must use either AES-128 or AES-256 for encryption.")
    assert len(hits) >= 1


def test_unresolved_depending_on_fires() -> None:
    hits = _unresolved_alternative_hits("Retention must be 30 or 90 days depending on account tier.")
    assert len(hits) >= 1


def test_unresolved_decision_required_clause_is_suppressed() -> None:
    hits = _unresolved_alternative_hits("DECISION_REQUIRED(encryption_algo): either AES-128 or AES-256.")
    assert hits == []


def test_unresolved_empty_text_returns_empty() -> None:
    assert _unresolved_alternative_hits("") == []


def test_matches_any_identical_clause_matches() -> None:
    assert _matches_any("must encrypt all backups at rest", ["must encrypt all backups at rest"])


def test_matches_any_near_duplicate_matches() -> None:
    assert _matches_any(
        "must encrypt all backups at rest",
        ["must encrypt all stored backups at rest using AES-256"],
    )


def test_matches_any_unrelated_clause_does_not_match() -> None:
    assert not _matches_any(
        "must encrypt all backups at rest",
        ["must support multi-factor authentication for all users"],
    )


def test_matches_any_short_candidate_returns_false() -> None:
    assert not _matches_any("encrypt", ["must encrypt all backups"])


def test_matches_any_empty_others_returns_false() -> None:
    assert not _matches_any("must encrypt all backups at rest", [])


def test_matches_any_short_distinct_security_clauses_do_not_collide() -> None:
    assert not _matches_any(
        "must encrypt stored data",
        ["must encrypt backups at rest"],
    )


def test_matches_authorized_removal_matching_text_suppresses() -> None:
    clause = "must encrypt all backups at rest"
    removal = "[REMOVE] The encryption at rest requirement is not applicable here."
    assert _matches_authorized_removal(clause, [removal])


def test_matches_authorized_removal_unrelated_removal_does_not_suppress() -> None:
    clause = "must encrypt all backups at rest"
    removal = "[REMOVE] The 30-day log retention clause is no longer required."
    assert not _matches_authorized_removal(clause, [removal])


def test_matches_authorized_removal_requires_exact_token_intersection() -> None:
    clause = "must encrypt all data at rest"
    removal = "[REMOVE] Drop the encryption default for sample fixtures."
    assert not _matches_authorized_removal(clause, [removal])


def test_matches_authorized_removal_empty_list_returns_false() -> None:
    assert not _matches_authorized_removal("must encrypt all backups at rest", [])


def test_matches_authorized_removal_none_returns_false() -> None:
    assert not _matches_authorized_removal("must encrypt all backups at rest", None)


def test_tokens_strips_stopwords() -> None:
    tokens = _tokens("must store data in the system")
    assert "the" not in tokens
    assert "in" not in tokens
    assert "store" in tokens or "stor" in tokens


def test_tokens_empty_text_returns_empty_set() -> None:
    assert _tokens("") == set()


def test_tokens_short_words_excluded() -> None:
    tokens = _tokens("it is OK to do it")
    assert "it" not in tokens
    assert "is" not in tokens


def test_classify_patch_classes_tagged_add() -> None:
    rows = classify_patch_classes(["[ADD] Must include audit logging."])
    assert rows[0]["patch_class"] == "ADD"


def test_classify_patch_classes_tagged_remove() -> None:
    rows = classify_patch_classes(["[REMOVE] The encryption clause is not needed."])
    assert rows[0]["patch_class"] == "REMOVE"


def test_classify_patch_classes_tagged_rewrite() -> None:
    rows = classify_patch_classes(["[REWRITE] Clarify the retention period."])
    assert rows[0]["patch_class"] == "REWRITE"


def test_classify_patch_classes_tagged_decision_required() -> None:
    rows = classify_patch_classes(["[DECISION_REQUIRED] Choose between AES-128 and AES-256."])
    assert rows[0]["patch_class"] == "DECISION_REQUIRED"


def test_classify_patch_classes_untagged_remove_inferred() -> None:
    rows = classify_patch_classes(["Drop the redundant encryption clause entirely."])
    assert rows[0]["patch_class"] == "REMOVE"


def test_classify_patch_classes_empty_list() -> None:
    assert classify_patch_classes([]) == []


def test_classify_patch_classes_empty_string_skipped() -> None:
    rows = classify_patch_classes(["", "  ", "[ADD] real patch"])
    assert len(rows) == 1
    assert rows[0]["patch_class"] == "ADD"


def _make_architect(
    requirement: str,
    assumptions: list[str] | None = None,
    open_questions: list[str] | None = None,
) -> dict[str, object]:
    return {
        "requirement": requirement,
        "changelog": ["changed"],
        "assumptions": assumptions or [],
        "open_questions": open_questions or [],
    }


def _make_auditor(patches: list[str] | None = None) -> dict[str, object]:
    return {
        "critique": ["c1"],
        "patches": patches or ["[ADD] p1"],
        "edge_cases": ["e1"],
        "test_gaps": ["t1"],
    }


def test_evaluate_valid_clean_requirement() -> None:
    result = evaluate_semantic_validity(
        architect_data=_make_architect("The system must encrypt all stored credentials at rest using AES-256."),
        auditor_data=_make_auditor(),
        previous_architect_data=None,
    )
    assert result["validity_verdict"] == "valid"
    assert result["semantic_failures"] == []


def test_evaluate_invalid_when_decision_required_present() -> None:
    result = evaluate_semantic_validity(
        architect_data=_make_architect("DECISION_REQUIRED(encryption_algo): algorithm not yet chosen."),
        auditor_data=_make_auditor(),
        previous_architect_data=None,
    )
    assert result["validity_verdict"] == "invalid"
    assert "pending_decisions" in result["semantic_failures"]
    assert result["pending_decision_count"] >= 1


def test_evaluate_optional_open_question_remains_valid() -> None:
    result = evaluate_semantic_validity(
        architect_data=_make_architect(
            "The system must encrypt all stored credentials using AES-256.",
            open_questions=["Should we also support ChaCha20 for mobile clients?"],
        ),
        auditor_data=_make_auditor(),
        previous_architect_data=None,
    )
    assert result["validity_verdict"] == "valid"
    assert result["pending_decision_count"] == 0
    assert result["open_question_count"] == 1


def test_evaluate_remove_patch_suppresses_demotion() -> None:
    result = evaluate_semantic_validity(
        architect_data=_make_architect("The system handles backups."),
        auditor_data=_make_auditor(patches=["[REMOVE] The encryption at rest clause is not applicable here."]),
        previous_architect_data=_make_architect("The system must encrypt all backups at rest."),
    )
    assert result["constraint_demotion_violations"] == []
    assert result["validity_verdict"] == "valid"


def test_evaluate_demotion_fires_without_remove_patch() -> None:
    result = evaluate_semantic_validity(
        architect_data=_make_architect(
            "The system handles backups.",
            assumptions=["All backups remain encrypted at rest."],
        ),
        auditor_data=_make_auditor(patches=["[ADD] add more constraints"]),
        previous_architect_data=_make_architect(
            "The system must encrypt all backups at rest.",
            assumptions=["All backups remain encrypted."],
        ),
    )
    assert len(result["constraint_demotion_violations"]) >= 1
    assert result["validity_verdict"] == "invalid"


def test_evaluate_no_previous_data_never_fires_demotion() -> None:
    result = evaluate_semantic_validity(
        architect_data=_make_architect("The system must encrypt all backups."),
        auditor_data=_make_auditor(),
        previous_architect_data=None,
    )
    assert result["constraint_demotion_violations"] == []
