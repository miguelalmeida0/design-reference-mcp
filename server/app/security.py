"""Network and origin restrictions for browsing untrusted sites."""
from urllib.parse import urlparse
import ipaddress
import socket

from app.catalog import is_allowed_reference_url


def publicly_routable_host(host: str) -> bool:
    h = host.lower().rstrip(".")
    if not h or h in {"localhost", "localhost.localdomain"} or h.endswith((".local", ".internal")):
        return False
    try:
        ip = ipaddress.ip_address(h)
        return ip.is_global
    except ValueError:
        pass
    try:
        addresses = socket.getaddrinfo(h, 443, type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(a[4][0]).is_global for a in addresses)
    except (socket.gaierror, ValueError):
        return False


def safe_navigation(url: str) -> bool:
    return is_allowed_reference_url(url) and publicly_routable_host(urlparse(url).hostname or "")


def is_private_subrequest(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return True
    host = parsed.hostname or ""
    if not host or host.lower() == "localhost" or host.endswith((".local", ".internal")):
        return True
    try:
        return not ipaddress.ip_address(host).is_global
    except ValueError:
        return False  # DNS-gated separately for top-level documents; no internal literals.

