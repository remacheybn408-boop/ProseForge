from __future__ import annotations

import ipaddress
from urllib.parse import urlparse


class EndpointPolicy:
    def __init__(self, allowed_local_hosts: tuple[str, ...] = ()):
        self.allowed_local_hosts = set(allowed_local_hosts)

    def validate(self, url: str, *, allow_local: bool = False) -> str:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("endpoint must be an http(s) URL without userinfo")
        host = parsed.hostname.lower().rstrip(".")
        local = host in {"localhost", "ip6-localhost"} or host == "127.0.0.1" or host == "::1"
        try:
            address = ipaddress.ip_address(host)
            local = local or address.is_private or address.is_loopback or address.is_link_local
        except ValueError:
            pass
        if local and not (allow_local and host in self.allowed_local_hosts):
            raise ValueError("local or private endpoint is not allowed")
        return parsed.geturl()
