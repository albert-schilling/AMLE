"""A locally run fetch with its own safety checks (user story 3.3).

Unlike the server-side ``web_fetch`` tool, this runs in our process, so the checks
below are the only sandbox: allowlisted https hosts, no redirects, no private
addresses, a timeout, a size cap and a content-type filter.

Known limit: the host is resolved once for the check and again by the HTTP client,
so DNS rebinding between the two is not covered.
"""

import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urlsplit

import httpx2

TIMEOUT_SECONDS = 5.0
MAX_BYTES = 100_000
ALLOWED_CONTENT_TYPES = ("application/json", "text/")


class FetchRefused(Exception):
    """A safety rule was broken; the message is safe to show the model."""


def resolve_host(host: str) -> list[str]:
    return [
        info[4][0] for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    ]


def check_url(
    url: str,
    allowed_hosts: set[str],
    resolve: Callable[[str], list[str]] = resolve_host,
) -> None:
    """Raise ``FetchRefused`` unless the URL is https, allowlisted and public."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()  # parsed, so no prefix tricks
    if parts.scheme != "https":
        raise FetchRefused("Only https URLs are allowed")
    if parts.username or parts.password:
        raise FetchRefused("URLs with credentials are not allowed")
    if parts.port not in (None, 443):
        raise FetchRefused("Only the default https port is allowed")
    if host not in allowed_hosts:
        raise FetchRefused(f"Host {host or '?'} is not on the allowlist")
    for address in resolve(host):
        if not ipaddress.ip_address(address).is_global:
            raise FetchRefused("Host resolves to a non-public address")


def fetch_text(
    url: str,
    allowed_hosts: set[str],
    client: httpx2.Client | None = None,
    resolve: Callable[[str], list[str]] = resolve_host,
) -> str:
    """GET one allowlisted URL and return its text, or raise ``FetchRefused``.

    Redirects are not followed: a redirect is refused instead of re-checked.
    """
    check_url(url, allowed_hosts, resolve)
    own_client = client is None
    client = client or httpx2.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False)
    try:
        with client.stream("GET", url) as response:
            if response.is_redirect:
                raise FetchRefused("Redirects are not followed")
            if response.status_code != 200:
                raise FetchRefused(f"HTTP {response.status_code}")
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith(ALLOWED_CONTENT_TYPES):
                raise FetchRefused(f"Content type {content_type or '?'} not allowed")
            body = b""
            for chunk in response.iter_bytes():
                body += chunk
                if len(body) > MAX_BYTES:
                    raise FetchRefused(f"Response larger than {MAX_BYTES} bytes")
            return body.decode(response.encoding or "utf-8", errors="replace")
    except httpx2.HTTPError as error:
        raise FetchRefused(f"Request failed: {type(error).__name__}") from error
    finally:
        if own_client:
            client.close()
