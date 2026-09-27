"""Pure fixture identities for generic SDK catalog restart proofs."""
from __future__ import annotations

from dataclasses import dataclass

BASE_CATALOG_ENTRY_FIELDS = (
    "workload_id", "workload_version", "entrypoint", "required_capabilities", "contract_style",
)


@dataclass(frozen=True)
class CatalogRoundtripProfile:
    name: str
    extension_id: str
    extension_version: str
    workload_id: str
    module_stem: str
    input_contract: str = ""
    output_contract: str = ""

    @property
    def entrypoint(self) -> str:
        return f"{self.module_stem}:JsonWorkload"

    @property
    def module_filename(self) -> str:
        return f"{self.module_stem}.py"

    @property
    def source_files(self) -> tuple[str, ...]:
        return (".gitattributes", "extension.json", self.module_filename)

    @property
    def catalog_entry_fields(self) -> tuple[str, ...]:
        fields = BASE_CATALOG_ENTRY_FIELDS
        if self.input_contract:
            fields += ("input_contract",)
        if self.output_contract:
            fields += ("output_contract",)
        return fields


def sdk_input() -> dict[str, int | str]:
    return {"seed": 41, "label": "restart"}


NULL_PROFILE = CatalogRoundtripProfile(
    name="null",
    extension_id="sdk.json.extension",
    extension_version="0.2.0",
    workload_id="sdk_json_v1",
    module_stem="sdk_json_extension",
)
EXPLICIT_PROFILE = CatalogRoundtripProfile(
    name="explicit",
    extension_id="sdk.explicit.extension",
    extension_version="0.2.1",
    workload_id="sdk_explicit_v1",
    module_stem="sdk_explicit_extension",
    input_contract="contracts/explicit-request.v1.json",
    output_contract="contracts/explicit-result.v1.json",
)
PROFILES = {profile.name: profile for profile in (NULL_PROFILE, EXPLICIT_PROFILE)}
