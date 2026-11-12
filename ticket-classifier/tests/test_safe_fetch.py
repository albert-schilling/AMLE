import httpx2
import pytest

from ticket_classifier.safe_fetch import MAX_BYTES, FetchRefused, fetch_text

HOSTS = {"status.mollie.com"}
URL = "https://status.mollie.com/api/v2/components.json"


def public(host):
    return ["93.184.216.34"]


def client_for(handler):
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def ok(request):
    return httpx2.Response(200, json={"components": []})


def test_fetch_returns_body():
    assert fetch_text(URL, HOSTS, client_for(ok), public) == '{"components":[]}'


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("http://status.mollie.com/x.json", "https"),
        ("https://evil.example.com/x.json", "allowlist"),
        ("https://status.mollie.com.evil.io/x.json", "allowlist"),  # prefix trick
        ("https://evil.io/?u=status.mollie.com", "allowlist"),
        ("https://user:pw@status.mollie.com/x.json", "credentials"),
        ("https://status.mollie.com:8443/x.json", "port"),
        ("ftp://status.mollie.com/x.json", "https"),
    ],
)
def test_fetch_refuses_bad_urls_without_a_request(url, message):
    def never(request):
        raise AssertionError("no request expected")

    with pytest.raises(FetchRefused, match=message):
        fetch_text(url, HOSTS, client_for(never), public)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.5", "169.254.169.254", "::1"])
def test_fetch_refuses_hosts_resolving_to_private_addresses(address):
    with pytest.raises(FetchRefused, match="non-public"):
        fetch_text(URL, HOSTS, client_for(ok), lambda host: [address])


def test_fetch_refuses_redirects():
    def redirect(request):
        return httpx2.Response(302, headers={"location": "https://evil.io/"})

    with pytest.raises(FetchRefused, match="Redirects"):
        fetch_text(URL, HOSTS, client_for(redirect), public)


def test_fetch_refuses_error_status():
    with pytest.raises(FetchRefused, match="HTTP 404"):
        fetch_text(URL, HOSTS, client_for(lambda r: httpx2.Response(404)), public)


def test_fetch_refuses_wrong_content_type():
    def binary(request):
        return httpx2.Response(
            200, content=b"x", headers={"content-type": "application/pdf"}
        )

    with pytest.raises(FetchRefused, match="Content type"):
        fetch_text(URL, HOSTS, client_for(binary), public)


def test_fetch_refuses_oversized_body():
    def big(request):
        return httpx2.Response(
            200, content=b"x" * (MAX_BYTES + 1), headers={"content-type": "text/plain"}
        )

    with pytest.raises(FetchRefused, match="larger"):
        fetch_text(URL, HOSTS, client_for(big), public)


def test_fetch_turns_timeouts_into_refusals():
    def slow(request):
        raise httpx2.ReadTimeout("slow")

    with pytest.raises(FetchRefused, match="ReadTimeout"):
        fetch_text(URL, HOSTS, client_for(slow), public)
