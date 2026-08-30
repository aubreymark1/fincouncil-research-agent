"""Network safety gates for public document retrieval."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit


class RetrievalSecurityError(ValueError):
    """Raised when a retrieval target is unsafe or outside the allowlist."""


def resolve_host_ips(host: str) -> list[str]:
    return sorted({item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})


def _is_public_ip(value: str) -> bool:
    address = ipaddress.ip_address(value)
    return address.is_global and not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_unspecified
    )


def validate_public_url(url: str, *, allowed_hosts: set[str]) -> object:
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https":
        raise RetrievalSecurityError("retrieval requires https")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        raise RetrievalSecurityError("retrieval URL has no hostname")
    normalised_hosts = {item.lower().rstrip(".") for item in allowed_hosts}
    if host not in normalised_hosts:
        raise RetrievalSecurityError(f"host {host!r} is not allowlisted")
    try:
        ips = [host]
        ipaddress.ip_address(host)
    except ValueError:
        try:
            ips = resolve_host_ips(host)
        except OSError as exc:
            raise RetrievalSecurityError("retrieval hostname could not be resolved") from exc
    if not ips or not all(_is_public_ip(value) for value in ips):
        raise RetrievalSecurityError("retrieval target resolves to a non-public address")
    return parsed
