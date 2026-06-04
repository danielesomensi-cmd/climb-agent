"""B255: verify gzip response compression.

Large JSON responses (e.g. /api/state ~1.9MB, the exercise catalog) must be
served with `Content-Encoding: gzip` when the client advertises gzip support.
Tiny responses below GZipMiddleware's minimum_size (1000 bytes) must NOT be
compressed, to avoid pointless overhead.

httpx (TestClient) sends `Accept-Encoding: gzip` by default and transparently
decodes the body, but the original `content-encoding` response header is
preserved — that is what we assert on.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def test_large_response_is_gzipped():
    """The exercise catalog is well over 1KB and must come back gzipped."""
    res = client.get(
        "/api/catalog/exercises",
        headers={"Accept-Encoding": "gzip"},
    )
    assert res.status_code == 200
    assert res.headers.get("content-encoding") == "gzip"
    # Body still decodes correctly (httpx auto-decompresses).
    assert isinstance(res.json(), (list, dict))


def test_small_response_not_gzipped():
    """/health is far below minimum_size (1000B) — must stay uncompressed."""
    res = client.get("/health", headers={"Accept-Encoding": "gzip"})
    assert res.status_code == 200
    assert res.headers.get("content-encoding") != "gzip"


def test_no_gzip_when_client_does_not_accept():
    """Client that does not advertise gzip must get an uncompressed body."""
    res = client.get(
        "/api/catalog/exercises",
        headers={"Accept-Encoding": "identity"},
    )
    assert res.status_code == 200
    assert res.headers.get("content-encoding") != "gzip"
