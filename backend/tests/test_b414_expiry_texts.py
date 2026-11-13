"""B414 (B414-6, INBOX-2026-11-02-d) — what the CLI and the coach say.

- The expiry of a real test, in the athlete context (CLI text and the coach
  block): «SCADE il …» / «SCADUTO il … — proponi …; non si azzera niente» /
  «PROROGATO al …», the warnings TEST_EXPIRING / TEST_EXPIRED (MAX_NOT_TESTED
  stays for a self-report only), the athlete's "Do the test" request — codes
  and dates only, never the free note. With any of them the retest section
  goes before the guards (the budget cut never loses it). ``VERSION`` b414.2.
- ``scripts/athlete_context.py --simulate``: an ALERT whose key belongs to the
  OTHER session names it («tocca CHIAVE x (data session_id)») instead of
  printing it after the draft's id (``key_refs``).
"""

from __future__ import annotations

from copy import deepcopy

from backend.engine import athlete_context as ac
from backend.engine import retest_policy as rp
from backend.tests import test_a289_retest_policy as a289
from backend.tests import test_a293_athlete_context_script as a293cli

OFFICIAL = "2026-09-24"


def _ctx(st: dict, day: str) -> dict:
    return ac.build_athlete_context(st, day, with_proposals=False, include_next_week=False)


def _postpone(until: str, **over) -> dict:
    rec = {"axis": "finger", "kind": "postpone", "trigger": "expiry", "official_date": OFFICIAL,
           "macrocycle_start": "2026-09-07", "until": until, "previous_until": None, "reason": "schedule",
           "note": "SECRET free text", "declined_at": "2026-12-10", "source": "app"}
    rec.update(over)
    return rec


def _codes(ctx: dict) -> dict:
    return {(w["code"], w.get("axis")) for w in ctx["warnings"]}


class TestAthleteContext:
    def test_version(self):
        assert ac.VERSION == "d287.1"

    def test_valid_far_from_the_expiry_says_only_the_date(self):
        ctx = _ctx(a289._daniele(), "2026-11-07")
        text = ac.render_text(ctx)
        assert "finger: ufficiale 116 kg (2026-09-24), massimale valido fino al 2026-12-22," in text
        assert "SCADE" not in text and "SCADUTO" not in text
        assert not {c for c, _a in _codes(ctx)} & {"TEST_EXPIRING", "TEST_EXPIRED"}
        assert "tested max valid until 2026-12-22;" in ac.render_coach_block(ctx)

    def test_expiring(self):
        ctx = _ctx(a289._daniele(), "2026-12-10")
        text = ac.render_text(ctx)
        assert ("massimale valido fino al 2026-12-22, SCADE il 2026-12-22 — proponi: fai il test o "
                "posticipa la scadenza") in text
        assert {("TEST_EXPIRING", "finger"), ("TEST_EXPIRING", "pulling")} <= _codes(ctx)
        assert ctx["maxima"][rp.PROTOCOL_HANG_7S]["expiring"] is True
        coach = ac.render_coach_block(ctx)
        assert "tested max valid until 2026-12-22: it EXPIRES soon — propose 'do the test' or " \
               "'postpone the expiry'" in coach

    def test_expired_nothing_is_reset(self):
        ctx = _ctx(a289._daniele(), "2026-12-23")
        text = ac.render_text(ctx)
        assert "SCADUTO il 2026-12-22 — proponi: fai il test o posticipa la scadenza; non si azzera niente" in text
        assert {("TEST_EXPIRED", "finger"), ("TEST_EXPIRED", "pulling")} <= _codes(ctx)
        assert "MAX_NOT_TESTED" not in {c for c, _a in _codes(ctx)}
        assert ac.athlete_is_tested(ctx)
        coach = ac.render_coach_block(ctx)
        assert "the tested max EXPIRED on 2026-12-22 — nothing is reset" in coach
        assert "expired 2026-12-22 (still the max until a new test)" in coach

    def test_postponed_expiry(self):
        st = a289._daniele()
        st[rp.DECLINES_KEY] = [_postpone("2027-01-19")]
        ctx = _ctx(st, "2026-12-23")
        text = ac.render_text(ctx)
        assert "finger: ufficiale 116 kg (2026-09-24), PROROGATO al 2027-01-19," in text
        assert "RINVIATO al 2027-01-19 (schedule)" in text
        assert ("TEST_EXPIRED", "finger") not in _codes(ctx) and ("TEST_EXPIRED", "pulling") in _codes(ctx)
        coach = ac.render_coach_block(ctx)
        assert "tested max valid until 2027-01-19 (expiry postponed by the athlete)" in coach
        # Expiring again 14 days before the new date.
        assert ("TEST_EXPIRING", "finger") in _codes(_ctx(st, "2027-01-05"))
        for out in (text, coach):
            assert "SECRET" not in out

    def test_request(self):
        st = a289._daniele()
        st[rp.DECLINES_KEY] = [{"axis": "finger", "kind": "request", "trigger": "requested",
                                "official_date": OFFICIAL, "macrocycle_start": "2026-09-07",
                                "requested_at": "2026-11-09", "source": "app"}]
        ctx = _ctx(st, "2026-11-09")
        assert "RICHIESTO il 2026-11-09 («fai il test» dell'atleta)" in ac.render_text(ctx)
        coach = ac.render_coach_block(ctx)
        assert "fingers: the athlete asked for the test on 2026-11-09 (do the test)" in coach

    def test_the_retest_section_survives_the_budget_cut(self):
        st = a289._daniele()
        ctx = _ctx(st, "2026-12-23")
        assert ac._retest_has_declines(ctx)
        coach = ac.render_coach_block(ctx)  # the default budget (A320: before the guards)
        assert len(coach) <= ac.COACH_BLOCK_MAX_CHARS
        assert "EXPIRED on 2026-12-22" in coach
        assert coach.index("Retest policy") < coach.index("Recovery guards")


class TestSimulateAttribution:
    def test_the_key_of_the_other_session_is_named(self):
        sim = a293cli.cli.simulate(a293cli._state(), a293cli.DRAFT, "2026-10-06", "evening")
        own = [a for a in sim["guard_alerts"] if a["session_id"] == "custom_cs_simulated_a293"]
        assert own and all(a["key_refs"] == [{"date": "2026-10-05", "slot": "evening",
                                               "session_id": "limit_boulder_gym", "key": "limit_power"}]
                           for a in own)
        out = a293cli.cli.render_simulation(sim)
        assert ("ALERT [finger_gap] 2026-10-06 evening: custom_cs_simulated_a293 — tocca CHIAVE limit_power "
                "(2026-10-05 limit_boulder_gym)") in out
        assert "custom_cs_simulated_a293 — CHIAVE limit_power" not in out
        # The A293 case (the flagged session holds the key) reads as before.
        assert "ALERT [finger_gap] 2026-10-07 evening: power_contact_gym — CHIAVE limit_power —" in out

    def test_an_alert_without_key_refs_reads_as_before(self):
        a = {"code": "finger_gap", "date": "2026-10-06", "slot": "evening", "session_id": "x", "key": ["k"],
             "message": "m"}
        assert a293cli.cli._alert_keys(deepcopy(a)) == " — CHIAVE k"
