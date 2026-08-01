"""A262 — public, unauthenticated assessment endpoint.

The engine's first endpoint with no auth in front of it, so the tests spend most
of their effort on the two things that would hurt: that it cannot be talked into
touching user state, and that it refuses input it cannot honestly score instead
of returning a plausible-looking wrong profile.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)

URL = "/api/public/assessment"

VALID = {
    "discipline": "lead",
    "current_grade": "7a",
    "target_grade": "7c",
    "max_rp": "7a",
    "max_os": "6b+",
    "climbing_years": 5,
    "primary_weakness": "fingers_give_out",
}

AXES = {
    "finger_strength",
    "pulling_strength",
    "power_endurance",
    "technique",
    "endurance",
}


class TestNoAuthNoState:
    def test_works_with_no_credentials_at_all(self):
        """No Authorization header, no X-User-ID: the whole point of the brief."""
        r = client.post(URL, json=VALID)
        assert r.status_code == 200, r.text
        assert set(r.json()["profile"]) == AXES

    def test_handler_never_touches_user_state(self, monkeypatch):
        """A write path here would be an unauthenticated write to somebody's
        account. Rather than asserting on side effects after the fact, make the
        storage layer explode if it is called at all."""
        import backend.api.deps as deps

        def boom(*args, **kwargs):  # pragma: no cover - must never run
            raise AssertionError("public assessment touched user state")

        monkeypatch.setattr(deps, "load_state", boom)
        monkeypatch.setattr(deps, "save_state", boom)

        assert client.post(URL, json=VALID).status_code == 200

    def test_response_admits_it_is_an_estimate(self):
        """Without measured tests the profile is derived from declared grades
        and self-report. The payload says so, so a client cannot present it as
        a measurement by omission."""
        assert client.post(URL, json=VALID).json()["estimated"] is True


class TestScoring:
    def test_axes_are_all_within_bounds(self):
        profile = client.post(URL, json=VALID).json()["profile"]
        assert all(0 <= v <= 100 for v in profile.values())
        assert all(isinstance(v, int) for v in profile.values())

    def test_weakest_axis_matches_the_profile(self):
        body = client.post(URL, json=VALID).json()
        profile = body["profile"]
        assert profile[body["weakest_axis"]] == min(profile.values())
        assert body["weakest_axis_label"]

    def test_declared_weakness_lowers_its_own_axis(self):
        """self_eval has to reach the engine — if the field were dropped the
        endpoint would still answer 200 with a subtly wrong profile."""
        without = client.post(URL, json={**VALID, "primary_weakness": None}).json()
        with_ = client.post(URL, json={**VALID, "primary_weakness": "fingers_give_out"}).json()
        assert with_["profile"]["finger_strength"] < without["profile"]["finger_strength"]

    def test_a_smaller_rp_os_gap_scores_better_technique(self):
        narrow = client.post(URL, json={**VALID, "max_rp": "7a", "max_os": "6c+"}).json()
        wide = client.post(URL, json={**VALID, "max_rp": "7a", "max_os": "5c"}).json()
        assert narrow["profile"]["technique"] > wide["profile"]["technique"]


class TestBoulder:
    def test_boulder_grades_are_mapped_to_the_lead_scale(self):
        """Font in, lead-calibrated scoring out — the same convention the
        onboarding and the mid-cycle discipline switch use, so a boulderer is
        measured against the same benchmarks as everyone else."""
        r = client.post(URL, json={
            "discipline": "boulder",
            "current_grade": "6C",
            "target_grade": "7B",
            "max_rp": "6C",
            "max_os": "6A+",
            "climbing_years": 5,
            "primary_weakness": None,
        })
        assert r.status_code == 200, r.text
        # 7B → 7c+ in BOULDER_TO_LEAD; echoed so the client renders the radar
        # against what was actually scored.
        assert r.json()["target_grade_lead"] == "7c+"

    def test_unknown_boulder_grade_is_rejected(self):
        r = client.post(URL, json={**VALID, "discipline": "boulder", "current_grade": "9Z"})
        assert r.status_code == 422


class TestRejectsWhatItCannotScore:
    def test_unknown_lead_grade_is_rejected(self):
        """grade_index() answers 0 for anything it does not know, which would
        silently produce a plausible, wrong score instead of an error."""
        r = client.post(URL, json={**VALID, "current_grade": "11z"})
        assert r.status_code == 422

    def test_onsight_harder_than_redpoint_is_rejected(self):
        """A negative gap lands in the `gap <= 2` bucket and reads as elite —
        the one input that scores *better* the more nonsensical it gets."""
        r = client.post(URL, json={**VALID, "max_rp": "6b", "max_os": "7c"})
        assert r.status_code == 422

    def test_missing_grades_are_rejected_rather_than_defaulted(self):
        """compute_assessment_profile() defaults to current 7a / target 7c+.
        Harmless for a validated user state, dishonest for a stranger who left
        the field blank: they would be handed someone else's profile."""
        payload = {k: v for k, v in VALID.items() if k != "target_grade"}
        assert client.post(URL, json=payload).status_code == 422

    def test_absurd_experience_is_rejected(self):
        assert client.post(URL, json={**VALID, "climbing_years": 999}).status_code == 422


class TestOptionalNumbers:
    """A263 — the tests that turn inferred axes into measured ones.

    Added by Daniele's review of the live page: it showed finger strength as
    the first axis and asked nothing about fingers, which for this audience is
    the fastest way to look unserious.
    """

    def test_max_hang_makes_finger_strength_measured(self):
        r = client.post(URL, json={
            **VALID,
            "primary_weakness": None,
            "bodyweight_kg": 70,
            "max_hang_added_kg": 30,
        })
        assert r.status_code == 200, r.text
        assert r.json()["measured_axes"] == ["finger_strength"]
        assert r.json()["estimated"] is False

    def test_a_stronger_hang_scores_higher(self):
        """Guards the added→total conversion: if the bodyweight were dropped,
        both would be scored against the engine's 70 kg fallback and the ratio
        would be wrong in the same direction for everyone."""
        weak = client.post(URL, json={
            **VALID, "primary_weakness": None,
            "bodyweight_kg": 70, "max_hang_added_kg": 0,
        }).json()
        strong = client.post(URL, json={
            **VALID, "primary_weakness": None,
            "bodyweight_kg": 70, "max_hang_added_kg": 40,
        }).json()
        assert strong["profile"]["finger_strength"] > weak["profile"]["finger_strength"]

    def test_assisted_hang_is_accepted_as_negative_added_weight(self):
        r = client.post(URL, json={
            **VALID, "bodyweight_kg": 70, "max_hang_added_kg": -15,
        })
        assert r.status_code == 200, r.text

    def test_pullup_makes_pulling_measured(self):
        r = client.post(URL, json={
            **VALID, "bodyweight_kg": 70, "weighted_pullup_added_kg": 35,
        })
        assert r.json()["measured_axes"] == ["pulling_strength"]

    def test_numbers_without_bodyweight_are_refused(self):
        """The engine falls back to 70 kg when bodyweight is missing. Scoring a
        stranger's hang against a stand-in bodyweight silently rescales their
        own number, so it is refused instead."""
        r = client.post(URL, json={**VALID, "max_hang_added_kg": 30})
        assert r.status_code == 422
        assert "bodyweight" in str(r.json()["detail"]).lower()

    def test_without_numbers_nothing_claims_to_be_measured(self):
        body = client.post(URL, json=VALID).json()
        assert body["measured_axes"] == []
        assert body["estimated"] is True
