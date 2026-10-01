from __future__ import annotations

import re

import pytest

import orket_extension_sdk as sdk

pytestmark = pytest.mark.contract


def test_sdk_version_exposed_from_package() -> None:
    assert isinstance(sdk.__version__, str)
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:a\d+|b\d+|rc\d+)?", sdk.__version__) is not None
