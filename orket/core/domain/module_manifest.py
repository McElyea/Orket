from __future__ import annotations

from pydantic import BaseModel, Field

MODULE_MANIFEST_CONTRACT_VERSION = "1.0.0"


class ModuleManifest(BaseModel):
    module_id: str
    module_version: str
    capabilities: list[str] = Field(default_factory=list)
    required_modules: list[str] = Field(default_factory=list)
    entrypoints: list[str] = Field(default_factory=list)
    contract_version_range: str = f">={MODULE_MANIFEST_CONTRACT_VERSION}"
