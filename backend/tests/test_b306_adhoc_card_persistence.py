"""B306 — the composed adhoc-session payload survives in coach history.

Before B306 the card lived only in client React state: `GET /coach/history`
returned bare text, so a PWA reload reduced a composed session to its summary
with no CTA. Now `append_coach_message` persists the payload and the history
row carries it back.
"""

from __future__ import annotations

import uuid

from backend.engine import storage

PAYLOAD = {
    "adhoc": True,
    "name": "Adhoc core + pull (home)",
    "exercises": [{"exercise_id": "pullup", "sets": 3}],
    "estimated_duration_minutes": 60,
}


def test_adhoc_session_roundtrips_through_history():
    uid = f"test-b306-{uuid.uuid4().hex[:8]}"
    storage.append_coach_message(uid, "user", "creami una sessione")
    storage.append_coach_message(uid, "assistant", "Ti ho preparato una sessione", adhoc_session=PAYLOAD)

    rows = storage.read_coach_messages(uid, limit=10)
    assert rows[0]["role"] == "assistant"
    assert rows[0]["adhoc_session"] == PAYLOAD
    # plain turns carry no payload key (file backend) or None (supabase)
    assert not rows[1].get("adhoc_session")


def test_plain_message_unaffected():
    uid = f"test-b306-{uuid.uuid4().hex[:8]}"
    row = storage.append_coach_message(uid, "assistant", "ciao")
    assert row["content"] == "ciao"
    rows = storage.read_coach_messages(uid, limit=5)
    assert not rows[0].get("adhoc_session")
