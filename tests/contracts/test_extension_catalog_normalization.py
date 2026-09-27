"""Contract: persisted extension styles select only their owned callable defaults."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from orket.extensions.catalog import ExtensionCatalog
from orket.extensions.models import CONTRACT_STYLE_LEGACY, CONTRACT_STYLE_SDK_V0, _ExtensionManifestEntry

pytestmark = pytest.mark.contract


# Layer: contract
@pytest.mark.parametrize(
    ("contract_style", "register_callable", "expected_style", "expected_register"),
    [
        pytest.param(CONTRACT_STYLE_SDK_V0, "", CONTRACT_STYLE_SDK_V0, "", id="sdk-empty"),
        pytest.param(CONTRACT_STYLE_SDK_V0, "sdk_register", CONTRACT_STYLE_SDK_V0,
                     "sdk_register", id="sdk-custom"),
        pytest.param(CONTRACT_STYLE_LEGACY, "", CONTRACT_STYLE_LEGACY, "register",
                     id="legacy-default"),
        pytest.param(CONTRACT_STYLE_LEGACY, "legacy_register", CONTRACT_STYLE_LEGACY,
                     "legacy_register", id="legacy-custom"),
        pytest.param("future_v2", "", "future_v2", "register", id="unknown-style"),
        pytest.param(None, "", "None", "register", id="null-style"),
        pytest.param(17, "", "17", "register", id="nonstring-style"),
    ],
)
def test_catalog_register_default_is_suppressed_only_for_exact_sdk_style(
    tmp_path: Path,
    contract_style: Any,
    register_callable: str,
    expected_style: str,
    expected_register: str,
) -> None:
    catalog_path = tmp_path / "catalog.json"
    payload = {
        "extensions": [{
            "extension_id": "style.boundary",
            "extension_version": "1.0.0",
            "source": "fixture",
            "contract_style": contract_style,
            "register_callable": register_callable,
            "manifest_entries": [],
        }],
    }
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")

    record, = ExtensionCatalog(catalog_path).list_extensions()

    assert (record.contract_style, record.register_callable) == (expected_style, expected_register)


# Layer: contract
@pytest.mark.parametrize(
    ("entry_style", "value", "expected"),
    [
        pytest.param(CONTRACT_STYLE_SDK_V0, None, "", id="sdk-null"),
        pytest.param(CONTRACT_STYLE_SDK_V0, "", "", id="sdk-empty"),
        pytest.param(CONTRACT_STYLE_SDK_V0, "None", "None", id="sdk-literal-none"),
        pytest.param(CONTRACT_STYLE_SDK_V0, False, "False", id="sdk-false"),
        pytest.param(CONTRACT_STYLE_SDK_V0, 0, "0", id="sdk-zero"),
        pytest.param(CONTRACT_STYLE_SDK_V0, " contract.ref.v1 ", "contract.ref.v1", id="sdk-reference"),
        pytest.param(CONTRACT_STYLE_LEGACY, None, "None", id="legacy-null-override"),
    ],
)
def test_catalog_sdk_optional_contract_normalization_is_none_only(
    tmp_path: Path,
    entry_style: str,
    value: Any,
    expected: str,
) -> None:
    catalog_path = tmp_path / "catalog.json"
    payload = {
        "extensions": [{
            "extension_id": "optional.contract.boundary",
            "extension_version": "1.0.0",
            "source": "fixture",
            "contract_style": CONTRACT_STYLE_SDK_V0,
            "register_callable": "",
            "manifest_entries": [{
                "workload_id": "optional_v1",
                "contract_style": entry_style,
                "input_contract": value,
                "output_contract": value,
            }],
        }],
    }
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")

    record, = ExtensionCatalog(catalog_path).list_extensions()
    entry, = record.manifest_entries

    assert entry.contract_style == entry_style
    assert (entry.input_contract, entry.output_contract) == (expected, expected)


# Layer: contract. The serializer must not expand non-SDK reference ownership.
@pytest.mark.parametrize("style", [CONTRACT_STYLE_LEGACY, "future_v2"])
def test_catalog_writer_preserves_non_sdk_compact_reference_boundary(style: str) -> None:
    entry = _ExtensionManifestEntry(
        workload_id="style-boundary",
        workload_version="1.0.0",
        entrypoint="fixture:run",
        required_capabilities=(),
        contract_style=style,
        input_contract="generic.input.v1",
        output_contract="generic.output.v1",
    )

    assert ExtensionCatalog._row_from_manifest_entry(entry) == {
        "workload_id": "style-boundary",
        "workload_version": "1.0.0",
        "entrypoint": "fixture:run",
        "required_capabilities": [],
        "contract_style": style,
    }
