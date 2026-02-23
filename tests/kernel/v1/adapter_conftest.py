# tests/kernel/v1/adapter_conftest.py
from __future__ import annotations

from pathlib import Path
import pytest

from tests.kernel.v1.adapter import LsiAdapter


@pytest.fixture
def lsi_tmp_home(tmp_path: Path) -> Path:
    # single root like <ORKET_HOME>
    return tmp_path / "orket_home"


@pytest.fixture
def lsi_adapter(lsi_tmp_home: Path) -> LsiAdapter:
    lsi_tmp_home.mkdir(parents=True, exist_ok=True)
    return LsiAdapter(lsi_tmp_home)
