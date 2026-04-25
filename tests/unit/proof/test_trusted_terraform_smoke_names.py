from __future__ import annotations

import pytest

from scripts.proof.trusted_terraform_smoke_names import (
    contains_placeholder,
    generate_bucket_name,
    generate_smoke_suffix,
    generate_table_name,
    validate_operator_names,
    validate_smoke_bucket_name,
    validate_smoke_table_name,
)

pytestmark = pytest.mark.unit


def test_same_seed_produces_same_suffix() -> None:
    assert generate_smoke_suffix("northstar-seed") == generate_smoke_suffix("northstar-seed")


def test_different_seeds_produce_different_suffixes() -> None:
    assert generate_smoke_suffix("northstar-a") != generate_smoke_suffix("northstar-b")


def test_generated_bucket_and_table_names_are_valid() -> None:
    validate_smoke_bucket_name(generate_bucket_name("northstar-seed"))
    validate_smoke_table_name(generate_table_name("northstar-seed"))


def test_placeholders_are_rejected() -> None:
    assert contains_placeholder("orket-smoke-<unique-suffix>")
    with pytest.raises(ValueError):
        validate_smoke_bucket_name("orket-smoke-<unique-suffix>")
    with pytest.raises(ValueError):
        validate_smoke_table_name("TerraformReviewsSmoke_<suffix>")


def test_operator_override_acceptance_and_rejection() -> None:
    validate_operator_names(bucket="valid-smoke-bucket-12345", table_name="TerraformReviewsSmoke_custom")
    with pytest.raises(ValueError):
        validate_operator_names(bucket="Invalid_Bucket", table_name="TerraformReviewsSmoke_custom")
