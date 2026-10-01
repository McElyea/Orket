import os

import pytest

pytestmark = pytest.mark.unit


# Layer: unit
def test_pytest_suite_disables_sandbox_creation_by_default() -> None:
    assert os.getenv("ORKET_DISABLE_SANDBOX") == "1"
