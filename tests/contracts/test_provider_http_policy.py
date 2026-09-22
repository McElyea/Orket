"""Layer: contract. Synthetic proxy compilation/refusal and redacted input repr."""
import pytest

from orket.core.contracts.provider_http import ProviderHttpInputs
from orket.decision_nodes.provider_http_policy import provider_proxy_mounts

pytestmark = pytest.mark.contract


@pytest.mark.parametrize(("environment", "expected"), [
    ({}, ()),
    ({"HTTP_PROXY": "upper", "http_proxy": "lower"}, (("http://", "http://lower"),)),
    ({"HTTP_PROXY": "upper", "http_proxy": ""}, ()),
    ({"HTTP_PROXY": "upper", "REQUEST_METHOD": "GET"}, ()),
    ({"HTTP_PROXY": "upper", "http_proxy": "lower", "REQUEST_METHOD": "GET"}, (("http://", "http://lower"),)),
    ({"HTTP_PROXY": "upper", "NO_PROXY": "example.com, *"}, ()),
    ({"NO_PROXY": "example.com,.example.org,127.0.0.1,::1,localhost,https://exact.test:123"}, (
        ("all://*example.com", None), ("all://*.example.org", None), ("all://127.0.0.1", None),
        ("all://[::1]", None), ("all://localhost", None), ("https://exact.test:123", None))),
])
def test_proxy_routes_are_pure_explicit_and_keep_precedence(environment, expected):
    assert provider_proxy_mounts(environment) == expected


def test_proxy_cidr_refuses_instead_of_claiming_subnet_bypass():
    with pytest.raises(ValueError, match="E_PROVIDER_HTTP_NO_PROXY_CIDR_UNSUPPORTED"):
        provider_proxy_mounts({"NO_PROXY": "192.168.0.0/16"})


def test_proxy_credentials_are_absent_from_input_repr():
    inputs = ProviderHttpInputs((("http://", "http://user:secret@proxy.test"),))
    assert "user" not in repr(inputs) and "secret" not in repr(inputs) and "proxy.test" not in repr(inputs)
