"""B393 — a `topped_out` attempt (top with rests) is not a send for milestones."""

from backend.engine.milestones_v1 import _route_sent


def test_topped_out_alone_is_not_sent():
    assert _route_sent({"attempts": [{"result": "topped_out"}, {"result": "fell"}]}) is False


def test_a_clean_send_still_counts():
    assert _route_sent({"attempts": [{"result": "topped_out"}, {"result": "sent"}]}) is True


def test_no_attempts_is_not_sent():
    assert _route_sent({}) is False
