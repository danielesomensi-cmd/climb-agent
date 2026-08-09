"""B328 — the coach must see the outdoor log as logged, not a grade list.

Before this brief `_logs_section` rendered an outdoor day as bare grades:

    - 2026-08-08: outdoor at Berdorf, climbs: 6c, 6c, 6c+, 7a+, 7a+, 6c

Everything a coach reasons from was gone: whether each attempt was sent or
fallen, how many attempts there were, the athlete's own notes — and the list
was truncated at 8 routes with no marker. A project day with two falls on an 8a
was indistinguishable from an 8a redpoint.
"""

from backend.coach.prompt_builder import (
    MAX_OUTDOOR_ROUTES_IN_LOG,
    INSTRUCTION_BLOCK,
    _outdoor_log_line,
)


def _route(grade, *results, name=None, style=None):
    r = {"grade": grade, "attempts": [{"result": x} for x in results]}
    if name:
        r["name"] = name
    if style:
        r["style"] = style
    return r


# The real Berdorf session of 2026-08-08 that exposed the bug.
BERDORF_08_08 = {
    "date": "2026-08-08",
    "spot_name": "Berdorf",
    "discipline": "lead",
    "duration_minutes": 120,
    "notes": "Long sessions with jinito e carlos",
    "routes": [
        _route("6c", "sent", name="Heintz"),
        _route("6c", "sent", name="6c near sirene"),
        _route("6c+", "sent", "sent", name="Willy"),
        _route("7a+", "sent", name="Caffidous"),
        _route("7a+", "sent", "sent", name="Voleur de spit"),
        _route("6c", "sent", name="Heintz"),
    ],
}

# 2026-08-05, same crag: a project day with two falls on an 8a.
BERDORF_08_05 = {
    "date": "2026-08-05",
    "spot_name": "Berdorf",
    "discipline": "lead",
    "day_type": "project",
    "duration_minutes": 120,
    "routes": [
        _route("6c", "sent", name="Heintz"),
        _route("8a", "fell", "fell", name="Cima Nikita"),
        _route("7b", "sent", name="Voleur de spit"),
    ],
}


class TestOutcomesSurvive:
    def test_falls_are_reported_as_falls(self):
        line = _outdoor_log_line(BERDORF_08_05)
        assert "Cima Nikita 8a fell x2" in line

    def test_a_fallen_project_is_never_rendered_as_sent(self):
        line = _outdoor_log_line(BERDORF_08_05)
        cima = [seg for seg in line.split(", ") if "Cima Nikita" in seg][0]
        assert "sent" not in cima

    def test_repeats_are_counted(self):
        line = _outdoor_log_line(BERDORF_08_08)
        assert "Willy 6c+ sent x2" in line
        assert "Voleur de spit 7a+ sent x2" in line

    def test_mixed_outcomes_on_one_route(self):
        line = _outdoor_log_line(
            {"date": "2026-08-01", "spot_name": "X", "discipline": "lead",
             "routes": [_route("7c", "fell", "fell", "sent", name="P")]}
        )
        assert "P 7c sent + fell x2" in line

    def test_attempt_count_is_explicit(self):
        assert "8 attempts over 6 routes" in _outdoor_log_line(BERDORF_08_08)


class TestNothingIsLostSilently:
    def test_athlete_notes_reach_the_prompt(self):
        assert "Long sessions with jinito e carlos" in _outdoor_log_line(BERDORF_08_08)

    def test_long_day_is_not_truncated_below_twelve_routes(self):
        entry = dict(BERDORF_08_08, routes=[_route("6c", "sent")] * 10)
        assert "not shown" not in _outdoor_log_line(entry)

    def test_truncation_is_announced_when_it_happens(self):
        entry = dict(BERDORF_08_08,
                     routes=[_route("6c", "sent")] * (MAX_OUTDOOR_ROUTES_IN_LOG + 5))
        assert "(+5 more routes not shown)" in _outdoor_log_line(entry)

    def test_day_type_and_discipline_are_kept(self):
        line = _outdoor_log_line(BERDORF_08_05)
        assert "outdoor lead at Berdorf" in line
        assert "project" in line


class TestDurationIsFlaggedNotTrusted:
    def test_duration_is_labelled_self_reported(self):
        line = _outdoor_log_line(BERDORF_08_08)
        assert "120 min self-reported" in line
        assert "not a density signal" in line

    def test_missing_duration_is_simply_absent(self):
        entry = {k: v for k, v in BERDORF_08_08.items() if k != "duration_minutes"}
        assert "self-reported" not in _outdoor_log_line(entry)

    def test_instruction_block_forbids_inferring_density(self):
        assert "Never infer density" in INSTRUCTION_BLOCK

    def test_instruction_block_forbids_upgrading_a_fall(self):
        assert "never upgrade a fall into a send" in INSTRUCTION_BLOCK


class TestDegradesGracefully:
    def test_entry_with_no_routes(self):
        line = _outdoor_log_line({"date": "2026-07-01", "spot_name": "Y",
                                  "discipline": "boulder", "routes": []})
        assert line.startswith("- 2026-07-01: outdoor boulder at Y")

    def test_routes_without_attempts_still_render(self):
        line = _outdoor_log_line({"date": "2026-07-02", "spot_name": "Y",
                                  "discipline": "lead",
                                  "routes": [{"grade": "7a"}]})
        assert "7a" in line
        assert "1 attempts over 1 routes" in line

    def test_unnamed_route_renders_grade_only(self):
        line = _outdoor_log_line({"date": "2026-07-03", "spot_name": "Y",
                                  "discipline": "lead",
                                  "routes": [_route("7a", "sent")]})
        assert "7a sent" in line

    def test_non_dict_route_is_skipped(self):
        line = _outdoor_log_line({"date": "2026-07-04", "spot_name": "Y",
                                  "discipline": "lead",
                                  "routes": ["garbage", _route("6a", "sent")]})
        assert "6a sent" in line
