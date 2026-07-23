"""Trusted-proxy client address handling tests."""

from starlette.requests import Request

from app.core.rate_limit import client_ip


def _request(peer: str, forwarded: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-forwarded-for", forwarded.encode())],
            "client": (peer, 12345),
            "server": ("test", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )


def test_trusted_proxy_uses_valid_forwarded_address():
    assert client_ip(_request("172.18.0.2", "203.0.113.8")) == "203.0.113.8"


def test_untrusted_peer_cannot_spoof_forwarded_address():
    assert client_ip(_request("198.51.100.4", "203.0.113.8")) == "198.51.100.4"
