"""B352 — stored custom sessions get `alt_sides` from the catalog on every read.

B324 stamps `alt_sides` when a custom session is saved, and the play-time
enrichment backfilled display fields only for exercises *without* cues. Sessions
saved between B283 (cues stored) and B324 (flag stored) therefore had cues and
no flag, and were never re-derived: replaying one from the builder, or adding it
to a day of the week plan, ran a Pallof press on one side only.
"""


def test_legacy_exercise_with_cues_but_no_flag_is_re_derived():
    from backend.api.routers.custom_session import enrich_custom_sessions_for_play

    legacy = [{
        "id": "cs_legacy",
        "name": "Work — montagna, core duro e braccia",
        "exercises": [
            {"exercise_id": "pallof_press", "sets": 3, "reps": 8, "cues": ["stored cue"]},
            {"exercise_id": "copenhagen_plank", "sets": 3, "work_seconds": 20, "cues": ["stored cue"]},
            {"exercise_id": "hollow_body_hold", "sets": 3, "work_seconds": 30, "cues": ["stored cue"]},
        ],
    }]

    out = enrich_custom_sessions_for_play(legacy)[0]["exercises"]

    assert [e["alt_sides"] for e in out] == [True, True, False]
    # The stored display fields are left alone — only laterality is re-derived.
    assert all(e["cues"] == ["stored cue"] for e in out)


def test_stale_flag_is_corrected_from_the_catalog():
    """The catalog is the source of truth, not what was stored."""
    from backend.api.routers.custom_session import enrich_custom_sessions_for_play

    stored = [{"id": "cs_x", "exercises": [
        {"exercise_id": "hollow_body_hold", "sets": 3, "cues": ["c"], "alt_sides": True},
    ]}]

    assert enrich_custom_sessions_for_play(stored)[0]["exercises"][0]["alt_sides"] is False


def test_read_path_does_not_mutate_the_stored_session():
    from backend.api.routers.custom_session import enrich_custom_sessions_for_play

    ex = {"exercise_id": "pallof_press", "sets": 3, "cues": ["c"]}
    stored = [{"id": "cs_x", "exercises": [ex]}]

    enrich_custom_sessions_for_play(stored)

    assert "alt_sides" not in ex


def test_unknown_exercise_is_not_side_alternating():
    from backend.api.routers.custom_session import enrich_custom_sessions_for_play

    stored = [{"id": "cs_x", "exercises": [{"exercise_id": "not_in_catalog", "sets": 1, "cues": ["c"]}]}]

    assert enrich_custom_sessions_for_play(stored)[0]["exercises"][0]["alt_sides"] is False
