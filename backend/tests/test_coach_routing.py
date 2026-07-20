"""Unit tests for backend.coach.routing.

Covers all 21 L3 routing rows from `backend/coach/knowledge/_index.md`
(the 21 routing rows together cover audit use cases UC1-UC15, UC17-UC19,
UC21-UC25). Also exercises fallback, ordering, cap, and the co-load rule.
"""

from pathlib import Path

import pytest

from backend.coach import routing
from backend.coach.routing import (
    CO_LOAD_TARGET,
    CO_LOAD_TRIGGER,
    FALLBACK_FILES,
    KNOWLEDGE_DIR,
    route_query,
)


@pytest.fixture(autouse=True)
def _clear_routing_cache():
    routing._clear_cache()
    yield
    routing._clear_cache()


def _names(paths):
    return [p.name for p in paths]


# ---------------------------------------------------------------------------
# Index loading
# ---------------------------------------------------------------------------


def test_index_loads_twentyone_rows():
    rows = routing._load_routing_table()
    assert len(rows) == 21


def test_index_rows_point_to_existing_files():
    rows = routing._load_routing_table()
    for row in rows:
        assert row.path.exists(), f"L3 file missing: {row.path}"


def test_index_rows_have_keywords():
    rows = routing._load_routing_table()
    for row in rows:
        assert row.keywords or row.multi_word_keywords, (
            f"row {row.path.name} has no keywords"
        )


# ---------------------------------------------------------------------------
# Per-UC routing (one query per L3 row, in row order)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query, expected_top",
    [
        # UC1
        ("How does the macrocycle deload work in periodization?", "01_periodization.md"),
        # UC2
        ("Should I do hangboard repeaters this week?", "02_finger_strength.md"),
        # UC3
        ("My weighted pull-up max is low, lock-off is weak", "03_pulling_strength.md"),
        # UC4
        ("I want to add 4x4 intervals for power endurance", "04_power_endurance.md"),
        # UC5
        ("Should I do ARC for capillaries and aerobic capacity?", "05_aerobic_endurance_arc.md"),
        # UC6
        ("Footwork drill — silent feet skill work", "06_technique_movement.md"),
        # UC7
        ("My fear of falling is killing my mental game", "07_mental_fear_focus.md"),
        # UC8
        ("Should I take creatine and collagen?", "08_nutrition.md"),
        # UC9
        ("Sleep is bad and I need a rest day, maybe G-Tox", "09_recovery_sleep.md"),
        # UC10
        ("My A2 pulley feels tweaked — finger pain on crimp", "10_injuries_fingers.md"),
        # UC11
        ("Shoulder impingement and epicondylitis in my elbow", "11_injuries_shoulder_elbow.md"),
        # UC12
        ("I need antagonist and postural prehab for extensor balance", "12_antagonist_postural.md"),
        # UC13
        ("Trip to Ceuse coming up, how do I taper for the redpoint?", "13_tapering_redpoint.md"),
        # UC14
        ("Menstrual cycle and youth teen training questions, also 40+ recovery", "14_female_age_youth.md"),
        # UC15
        ("My motivation is gone, hit a plateau, what are my values?", "15_goal_setting_motivation.md"),
        # UC18 (row 16)
        ("What does my assessment 5-axis radar percentile score mean?", "16_assessment_interpretation.md"),
        # UC17/UC21 (row 17)
        ("My RPE is up, feeling overtraining, ACWR creeping, resting HR high", "17_readiness_overtraining.md"),
        # UC19 (row 18)
        ("I am traveling with no equipment, need a minimum home alternative", "18_equipment_fallback.md"),
        # UC22 (row 19)
        ("Concurrent running plus work stress and lifestyle juggling", "19_lifestyle_integration.md"),
        # UC23 (row 20)
        ("Back to training after a long break, detraining restart from illness", "20_return_to_training.md"),
        # UC24 (row 21) — commercial-gym session composition
        ("I'm at a commercial gym today, build me a workout with dumbbells and a bench", "21_adhoc_gym_sessions.md"),
        # UC25 (row 21) — off-plan swap
        ("I don't feel like today's session, I'd rather do something else at the gym", "21_adhoc_gym_sessions.md"),
    ],
)
def test_per_uc_routing(query, expected_top):
    paths = route_query(query)
    assert paths, f"no routing for {query!r}"
    assert paths[0].name == expected_top, (
        f"query {query!r}: expected top={expected_top}, got {_names(paths)}"
    )


# ---------------------------------------------------------------------------
# Fallback behavior
# ---------------------------------------------------------------------------


def test_fallback_on_zero_match():
    paths = route_query("xyzzy plugh frobnicate quux")
    assert _names(paths) == [p.name for p in FALLBACK_FILES]


def test_fallback_respects_max_files_cap():
    paths = route_query("xyzzy plugh frobnicate", max_files=1)
    assert len(paths) == 1
    assert paths[0].name == FALLBACK_FILES[0].name


def test_fallback_is_skipped_when_at_least_one_keyword_matches():
    # "phase" alone is a single keyword in 01_periodization — should not
    # trigger the fallback pair, even though the rest of the query is noise.
    paths = route_query("phase")
    assert _names(paths) == ["01_periodization.md"]


# ---------------------------------------------------------------------------
# Ranking and cap
# ---------------------------------------------------------------------------


def test_higher_score_wins():
    # 02_finger_strength has both "hangboard" and "repeater"; 01_periodization
    # has none of those terms. 02 must rank first when both are present.
    paths = route_query("hangboard repeater session today")
    assert paths[0].name == "02_finger_strength.md"


def test_max_files_cap_respected():
    # Query with keywords spanning many files: should still cap at 3 by default.
    query = "phase hangboard pull-up ARC footwork fear creatine sleep pulley shoulder antagonist taper youth motivation"
    paths = route_query(query)
    assert len(paths) <= 3


def test_max_files_cap_explicit_one():
    paths = route_query("phase hangboard pull-up ARC sleep", max_files=1)
    assert len(paths) == 1


def test_max_files_zero_returns_empty():
    paths = route_query("phase hangboard", max_files=0)
    assert paths == []


def test_ties_broken_by_index_order():
    # "phase" → 01; "edge" → 02. Both score 1. Row order in _index.md puts
    # 01 before 02, so 01 must come first.
    paths = route_query("phase edge")
    assert _names(paths)[0] == "01_periodization.md"
    assert "02_finger_strength.md" in _names(paths)


# ---------------------------------------------------------------------------
# Co-load rule (10_injuries_fingers + 02_finger_strength)
# ---------------------------------------------------------------------------


def test_co_load_injuries_fingers_with_finger_strength_keyword():
    # "A2 tweak" routes to 10_injuries_fingers; "max hang" is a keyword in
    # 02_finger_strength. Both must be present.
    paths = route_query("A2 tweak from a max hang session")
    names = _names(paths)
    assert CO_LOAD_TRIGGER in names
    assert CO_LOAD_TARGET in names


def test_no_co_load_when_finger_strength_keyword_absent():
    # Pulley pain with no exercise/test keyword — 02_finger_strength must
    # NOT be force-loaded.
    paths = route_query("my pulley hurts on the crimp, lumbrical issue")
    names = _names(paths)
    assert CO_LOAD_TRIGGER in names
    # 02 may or may not appear via natural scoring; the co-load shouldn't
    # add it artificially.
    if CO_LOAD_TARGET in names:
        # then it must be because the natural scorer picked it up — but
        # this query has no finger_strength keywords, so it should NOT.
        pytest.fail(
            "02_finger_strength force-loaded without finger-strength keyword"
        )


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


def test_case_insensitive_matching():
    paths_upper = route_query("HANGBOARD REPEATERS")
    paths_lower = route_query("hangboard repeaters")
    assert _names(paths_upper) == _names(paths_lower)


def test_punctuation_does_not_block_match():
    paths = route_query("Should I do hangboard? Repeaters!")
    assert paths[0].name == "02_finger_strength.md"


def test_returns_paths_under_knowledge_dir():
    paths = route_query("hangboard repeaters")
    for p in paths:
        assert KNOWLEDGE_DIR in p.parents, f"{p} not under {KNOWLEDGE_DIR}"


def test_empty_query_falls_back():
    paths = route_query("")
    assert _names(paths) == [p.name for p in FALLBACK_FILES]


def test_caching_returns_identical_table():
    rows1 = routing._load_routing_table()
    rows2 = routing._load_routing_table()
    assert rows1 is rows2


def test_missing_index_returns_empty(monkeypatch, tmp_path):
    bogus = tmp_path / "does_not_exist.md"
    monkeypatch.setattr(routing, "INDEX_PATH", bogus)
    routing._clear_cache()
    assert route_query("hangboard") == []


# ---------------------------------------------------------------------------
# C259 — Italian keyword routing (D253 §2.2/§3.2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query, expected_top",
    [
        # The five acceptance queries from the C-KB-ROUTING-IT brief.
        ("scheda per la trave", "02_finger_strength.md"),
        ("settimana di scarico", "01_periodization.md"),
        ("dolore alla puleggia", "10_injuries_fingers.md"),
        ("sono in stallo", "15_goal_setting_motivation.md"),
        ("resistenza per il lavorato", "05_aerobic_endurance_arc.md"),
        # A few more single-intent Italian queries across other rows.
        ("ho paura di cadere durante il volo", "07_mental_fear_focus.md"),
        ("creami una sessione in palestra con i manubri", "21_adhoc_gym_sessions.md"),
        ("come miglioro la tecnica sui piedi", "06_technique_movement.md"),
        ("mi alleno le trazioni per il bloccaggio", "03_pulling_strength.md"),
        ("sono sempre stanco, forse sovrallenamento", "17_readiness_overtraining.md"),
    ],
)
def test_italian_routing(query, expected_top):
    paths = route_query(query)
    assert paths, f"no routing for {query!r}"
    assert paths[0].name == expected_top, (
        f"query {query!r}: expected top={expected_top}, got {_names(paths)}"
    )


def test_italian_body_part_disambiguation():
    # "dolore" lives on both finger (10) and shoulder/elbow (11) rows; the
    # body-part term must break the tie to the right file.
    assert route_query("dolore alla spalla")[0].name == "11_injuries_shoulder_elbow.md"
    assert route_query("dolore alle dita")[0].name == "10_injuries_fingers.md"
    assert route_query("dolore alla puleggia")[0].name == "10_injuries_fingers.md"


def test_mixed_language_query_routes_sensibly():
    # Either language's keywords should hit — here EN "hangboard" and IT
    # "forza dita" both point at finger strength.
    paths = route_query("hangboard session per la forza dita")
    assert paths[0].name == "02_finger_strength.md"


def test_italian_offtopic_still_falls_back():
    # Genuinely off-topic Italian text matches no keyword row → fallback pair.
    paths = route_query("che bella giornata di sole oggi al mare")
    assert _names(paths) == [p.name for p in FALLBACK_FILES]


def test_singleword_keywords_survive_tokenization():
    # The query tokenizer ([a-z0-9+×x]+) drops accented letters, so an
    # accented single-word keyword (e.g. "continuità" → "continuit") could
    # never match a real query. Invariant: every single-word keyword must
    # tokenize back to itself as one intact token. (Multi-word keywords are
    # substring-matched on the raw lowercased query and are exempt.)
    rows = routing._load_routing_table()
    for row in rows:
        for kw in row.keywords:
            assert kw in routing._tokenize(kw), (
                f"single-word keyword {kw!r} in {row.path.name} is not "
                "recoverable by the query tokenizer (accented/unsupported char)"
            )
