from __future__ import annotations

import pytest

from orket.exceptions import LeaseNotAvailableError, OrketError, SettingsBridgeError

pytestmark = pytest.mark.unit


def test_infrastructure_and_settings_errors_are_orket_errors() -> None:
    """Layer: unit. Verifies infrastructure errors are caught by the Orket domain base class."""
    assert issubclass(LeaseNotAvailableError, OrketError)
    assert issubclass(SettingsBridgeError, OrketError)

    with pytest.raises(OrketError):
        raise LeaseNotAvailableError("lease unavailable")

    with pytest.raises(OrketError):
        raise SettingsBridgeError("settings bridge unavailable")
