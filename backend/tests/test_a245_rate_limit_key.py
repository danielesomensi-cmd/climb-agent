"""A245 E-1 (B4) — the rate-limit key must not be the proxy's IP.

Behind Railway's load balancer `get_remote_address` returns the balancer for
every request, so every per-IP limit was effectively a shared global limit: one
busy user could 429 everybody. These tests pin the replacement key.
"""

from types import SimpleNamespace

from backend.api.rate_limit import rate_limit_key, _client_ip


def _request(headers=None, client_host="10.0.0.1", **state):
    """Minimal stand-in for a Starlette Request (only what the key func reads)."""
    return SimpleNamespace(
        headers={k: v for k, v in (headers or {}).items()},
        client=SimpleNamespace(host=client_host, port=1234),
        state=SimpleNamespace(**state),
        scope={"client": (client_host, 1234), "headers": []},
    )


class TestRateLimitKey:
    def test_authenticated_requests_key_on_the_user(self):
        req = _request(user_id="user-abc")
        assert rate_limit_key(req) == "user:user-abc"

    def test_two_users_behind_one_proxy_get_separate_buckets(self):
        proxy = {"X-Forwarded-For": "203.0.113.9"}
        a = rate_limit_key(_request(headers=proxy, user_id="user-a"))
        b = rate_limit_key(_request(headers=proxy, user_id="user-b"))
        assert a != b

    def test_anonymous_requests_fall_back_to_the_forwarded_client_ip(self):
        req = _request(headers={"X-Forwarded-For": "203.0.113.9"})
        assert rate_limit_key(req) == "ip:203.0.113.9"

    def test_forwarded_for_uses_the_leftmost_entry(self):
        # <client>, <proxy1>, <proxy2> — only the first is the real client.
        req = _request(headers={"X-Forwarded-For": "203.0.113.9, 70.41.3.18, 150.172.238.178"})
        assert _client_ip(req) == "203.0.113.9"

    def test_two_anonymous_clients_behind_one_proxy_are_not_merged(self):
        a = rate_limit_key(_request(headers={"X-Forwarded-For": "203.0.113.9"}))
        b = rate_limit_key(_request(headers={"X-Forwarded-For": "198.51.100.4"}))
        assert a != b

    def test_falls_back_to_peer_address_without_the_header(self):
        assert rate_limit_key(_request(client_host="192.0.2.7")) == "ip:192.0.2.7"

    def test_blank_forwarded_for_does_not_produce_an_empty_key(self):
        req = _request(headers={"X-Forwarded-For": "  "}, client_host="192.0.2.7")
        assert rate_limit_key(req) == "ip:192.0.2.7"

    def test_user_key_wins_over_ip_even_when_both_are_available(self):
        req = _request(headers={"X-Forwarded-For": "203.0.113.9"}, user_id="user-abc")
        assert rate_limit_key(req) == "user:user-abc"
