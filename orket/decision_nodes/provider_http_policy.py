"""Compile captured proxy inputs to HTTPX's public mount configuration."""
from collections.abc import Mapping
from ipaddress import ip_address


def provider_proxy_mounts(environment: Mapping[str, str]) -> tuple[tuple[str, str | None], ...]:
    # Match urllib's lowercase precedence and CGI HTTP_PROXY protection without
    # consulting ambient environment or the operating system proxy registry.
    proxies = {name.lower()[:-6]: value for name, value in environment.items()
               if name.lower().endswith("_proxy") and value}
    if "REQUEST_METHOD" in environment:
        proxies.pop("http", None)
    for name, value in environment.items():
        if name.endswith("_proxy"):
            if value:
                proxies[name.lower()[:-6]] = value
            else:
                proxies.pop(name.lower()[:-6], None)
    bypass = [host.strip() for host in proxies.get("no", "").split(",") if host.strip()]
    if "*" in bypass:
        return ()
    mounts = {f"{scheme}://": value if "://" in value else f"http://{value}"
              for scheme in ("http", "https", "all") if (value := proxies.get(scheme))}
    for host in bypass:
        if "://" in host:
            pattern = host
        elif "/" in host:
            # HTTPX URL patterns do not implement CIDR range matching.
            raise ValueError("E_PROVIDER_HTTP_NO_PROXY_CIDR_UNSUPPORTED")
        else:
            try:
                address = ip_address(host)
            except ValueError:
                pattern = f"all://{host}" if host.lower() == "localhost" else f"all://*{host}"
            else:
                pattern = f"all://[{host}]" if address.version == 6 else f"all://{host}"
        mounts[pattern] = None
    return tuple(mounts.items())
