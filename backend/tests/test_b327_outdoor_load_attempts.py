"""B327 — outdoor load score: attempts-based volume, no duration factor.

The D151 formula (avg over routes × volume_factor(routes) × duration_factor)
mis-scored three real sessions logged from Berdorf:

  * a 6-route / 8-ascent volume day scored 22, while a 3-route project day the
    same week scored 24 — the longer day weighed less;
  * repeats were free: two ascents of the same route counted once;
  * a day logged with its real duration (rests included) scored ~55% higher
    than the identical day logged at the 120 min default — resting more read as
    training harder.

These tests pin the corrected behaviour.
"""

from typing import Any, Dict, List

from backend.engine.outdoor_log import compute_outdoor_load_score


def _entry(routes: List[Dict[str, Any]], duration_minutes: int = 120) -> Dict[str, Any]:
    return {
        "log_version": "outdoor.v2",
        "date": "2026-08-08",
        "spot_name": "Berdorf",
        "discipline": "lead",
        "duration_minutes": duration_minutes,
        "routes": routes,
    }


def _route(grade: str, *results: str) -> Dict[str, Any]:
    return {"name": grade, "grade": grade,
            "attempts": [{"result": r} for r in results]}


# Berdorf, 2026-08-08 — 6 routes, 8 ascents, nothing dropped.
_VOLUME_DAY = [
    _route("6c", "sent"),
    _route("6c", "sent"),
    _route("6c+", "sent", "sent"),
    _route("7a+", "sent"),
    _route("7a+", "sent", "sent"),
    _route("6c", "sent"),
]
# Berdorf, 2026-08-05 — 3 routes, 4 attempts, two burns on an 8a project.
_PROJECT_DAY = [
    _route("6c", "sent"),
    _route("8a", "fell", "fell"),
    _route("7b", "sent"),
]


class TestDurationNoLongerInflatesLoad:
    def test_same_climbing_logged_with_longer_rests_scores_the_same(self):
        tight = compute_outdoor_load_score(_entry(_VOLUME_DAY, duration_minutes=120))
        with_rests = compute_outdoor_load_score(_entry(_VOLUME_DAY, duration_minutes=300))
        assert tight == with_rests

    def test_missing_duration_is_not_penalised(self):
        no_duration = dict(_entry(_VOLUME_DAY))
        no_duration.pop("duration_minutes")
        assert compute_outdoor_load_score(no_duration) == compute_outdoor_load_score(
            _entry(_VOLUME_DAY)
        )


class TestAttemptsDriveVolume:
    def test_repeat_ascent_counts_twice(self):
        once = compute_outdoor_load_score(_entry([_route("7a", "sent")]))
        twice = compute_outdoor_load_score(_entry([_route("7a", "sent", "sent")]))
        assert twice > once

    def test_project_burns_on_one_route_are_not_free(self):
        one_burn = compute_outdoor_load_score(_entry([_route("8a", "fell")]))
        six_burns = compute_outdoor_load_score(
            _entry([_route("8a", "fell", "fell", "fell", "fell", "fell", "sent")])
        )
        assert six_burns > one_burn * 1.5

    def test_fall_counts_less_than_send_at_equal_grade(self):
        sent = compute_outdoor_load_score(_entry([_route("7b", "sent")]))
        fell = compute_outdoor_load_score(_entry([_route("7b", "fell")]))
        assert fell < sent

    def test_route_without_attempts_counts_as_one_ascent(self):
        """outdoor.v1 logs and hand-written entries omit `attempts` entirely."""
        bare = compute_outdoor_load_score(_entry([{"name": "R", "grade": "7a"}]))
        explicit = compute_outdoor_load_score(_entry([_route("7a", "sent")]))
        assert bare == explicit

    def test_empty_attempts_list_also_counts_as_one_ascent(self):
        """`attempts` defaults to [] in OutdoorRoute — an empty list means the
        client logged the route without per-attempt detail, NOT zero climbing."""
        empty = compute_outdoor_load_score(_entry([{"grade": "7a", "attempts": []}]))
        explicit = compute_outdoor_load_score(_entry([_route("7a", "sent")]))
        assert empty == explicit


class TestVolumeDayOutweighsShorterProjectDay:
    def test_eight_ascent_day_scores_above_four_attempt_day(self):
        """The regression that started B327: 22 vs 24, the wrong way round."""
        volume = compute_outdoor_load_score(_entry(_VOLUME_DAY))
        project = compute_outdoor_load_score(_entry(_PROJECT_DAY))
        assert volume > project

    def test_both_days_stay_in_a_plausible_band(self):
        for routes in (_VOLUME_DAY, _PROJECT_DAY):
            score = compute_outdoor_load_score(_entry(routes))
            assert 20 <= score <= 60


class TestUnchangedGuarantees:
    def test_empty_routes_zero(self):
        assert compute_outdoor_load_score(_entry([])) == 0

    def test_cap_holds(self):
        monster = [_route("9a", *(["sent"] * 10)) for _ in range(10)]
        assert compute_outdoor_load_score(_entry(monster)) <= 85

    def test_determinism(self):
        e = _entry(_VOLUME_DAY)
        assert compute_outdoor_load_score(e) == compute_outdoor_load_score(e)
