"""Explicit first-run provider choices; runtime defaults remain in provider_runtime."""
from dataclasses import dataclass
from urllib.parse import urlsplit

from orket.core.contracts.provider_runtime import normalize_base_url, normalize_provider


def validate_provider_endpoint(value: str) -> str:
    url = urlsplit(value)
    if (url.scheme not in {"http", "https"} or not url.hostname or url.username is not None
            or url.password is not None or url.query or url.fragment):
        raise ValueError("E_SETUP_PROVIDER_URL_INVALID: use an HTTP(S) endpoint without credentials or query")
    return normalize_base_url(value, default=value)


@dataclass(frozen=True)
class ProviderSetup:
    provider: str
    model: str
    base_url: str
    gguf_root: str = ""

    def __post_init__(self) -> None:
        normalize_provider(self.provider)
        for value in (self.provider, self.model, self.base_url, self.gguf_root):
            if any(character in value for character in ("\r", "\n", "\0", "${")):
                raise ValueError("E_SETUP_PROVIDER_VALUE_INVALID")
        if not self.model.strip():
            raise ValueError("E_SETUP_MODEL_REQUIRED")
        if self.provider == "llama_cpp" and not self.gguf_root.strip():
            raise ValueError("E_SETUP_GGUF_ROOT_REQUIRED: select the directory containing your GGUF files")
        object.__setattr__(self, "base_url", validate_provider_endpoint(self.base_url))

    def environment_values(self) -> dict[str, str]:
        endpoint_key = {"llama_cpp": "ORKET_LLM_LLAMA_CPP_BASE_URL", "ollama": "ORKET_LLM_OLLAMA_HOST"}.get(
            self.provider, "ORKET_LLM_OPENAI_BASE_URL")
        values = {"ORKET_LLM_PROVIDER": self.provider, endpoint_key: self.base_url,
                  "ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL": "0", "ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL": "0"}
        if self.provider == "llama_cpp":
            values["ORKET_LLAMA_CPP_GGUF_MODEL_ROOT"] = self.gguf_root
        return values
