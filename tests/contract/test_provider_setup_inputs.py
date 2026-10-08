"""Pure setup-input admission; these controls do not establish Mac/provider operation."""
import pytest

from orket.core.contracts.provider_setup import ProviderSetup

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("changes", [
    {"provider": "unknown"}, {"model": ""}, {"model": "${SECRET}"}, {"gguf_root": ""},
    {"base_url": "https://user:secret@localhost/v1"}, {"base_url": "http://localhost/v1?key=secret"},
    {"base_url": "file:///models"}, {"model": "model\nOTHER=1"},
])
def test_invalid_setup_choices_refuse_without_echoing_credentials(changes):
    inputs = dict(provider="llama_cpp", model="model", base_url="http://localhost:8080/v1", gguf_root="models")
    with pytest.raises(ValueError) as error:
        ProviderSetup(**(inputs | changes))
    assert "secret" not in str(error.value)
