"""B353: a dead Supabase connection must not end the user's ability to save.

Production symptom: uploading a ~750 KB user_state over supabase-py's HTTP/2
client died with `RemoteProtocolError: ConnectionTerminated`, and every later
write on that pooled connection failed the same way — PUT /api/state returned
500 for hours while small requests kept working.
"""

import httpx
import pytest

from backend.engine import storage_supabase as ss


def test_retry_recovers_from_a_transient_transport_error(monkeypatch):
    calls = {"n": 0, "rebuilds": 0}

    def op():
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.RemoteProtocolError("ConnectionTerminated")
        return "ok"

    monkeypatch.setattr(ss, "_url", "https://example.supabase.co")
    monkeypatch.setattr(ss, "_key", "service-key")
    monkeypatch.setattr(ss, "_build_client", lambda u, k: calls.__setitem__("rebuilds", calls["rebuilds"] + 1))
    monkeypatch.setattr(ss.time, "sleep", lambda _s: None)

    assert ss._retry(op, what="test") == "ok"
    assert calls["n"] == 2
    # The poisoned pool is dropped, not reused.
    assert calls["rebuilds"] == 1


def test_retry_gives_up_after_the_last_attempt(monkeypatch):
    monkeypatch.setattr(ss, "_url", "")
    monkeypatch.setattr(ss, "_key", "")
    monkeypatch.setattr(ss.time, "sleep", lambda _s: None)

    def always_dead():
        raise httpx.RemoteProtocolError("ConnectionTerminated")

    with pytest.raises(httpx.RemoteProtocolError):
        ss._retry(always_dead, what="test", attempts=3)


def test_retry_does_not_swallow_an_answer_from_postgrest(monkeypatch):
    """A 4xx/5xx is a reply, not a broken pipe — retrying it only adds latency."""
    calls = {"n": 0}

    def op():
        calls["n"] += 1
        raise ValueError("duplicate key value violates unique constraint")

    monkeypatch.setattr(ss.time, "sleep", lambda _s: None)
    with pytest.raises(ValueError):
        ss._retry(op, what="test")
    assert calls["n"] == 1


def test_client_is_built_without_http2():
    """HTTP/2 stream flow control is what stalled; HTTP/1.1 has none."""
    import inspect

    src = inspect.getsource(ss._build_client)
    assert "http2=False" in src
