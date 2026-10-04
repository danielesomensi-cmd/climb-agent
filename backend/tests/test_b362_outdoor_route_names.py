"""B362 — one route, one name in the outdoor log.

Daniele's Berdorf history had "Cima nikita" next to "Cima Nikita" and "Bibi "
(trailing space) next to "Bibi": the outdoor report keyed routes on the exact
string, so one project showed up as two rows with split attempt counts. On save,
a name that matches an earlier route at the same crag case/whitespace-
insensitively now takes the earlier spelling.
"""
from __future__ import annotations

from typing import Any, Dict, List

import pytest

from backend.engine.outdoor_log import (
    append_outdoor_session,
    canonicalize_route_names,
    load_outdoor_sessions,
    update_outdoor_session,
)


def _entry(date: str, names: List[str], spot: str = "Berdorf") -> Dict[str, Any]:
    return {
        "log_version": "outdoor.v2",
        "date": date,
        "spot_name": spot,
        "discipline": "lead",
        "duration_minutes": 120,
        "routes": [
            {"name": n, "grade": "7a", "attempts": [{"result": "fell"}]} for n in names
        ],
    }


@pytest.fixture
def tmp_log_dir(tmp_path, monkeypatch):
    from backend.engine import storage
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    yield tmp_path


def test_case_and_whitespace_variants_take_the_logged_spelling():
    history = [_entry("2026-07-01", ["Cima Nikita"]), _entry("2026-07-02", ["Cima Nikita"])]
    e = canonicalize_route_names(_entry("2026-07-03", ["cima  nikita ", "Bibi "]), history)
    assert [r["name"] for r in e["routes"]] == ["Cima Nikita", "Bibi"]


def test_most_frequent_spelling_wins():
    history = [
        _entry("2026-06-01", ["Cima nikita"]),
        _entry("2026-07-01", ["Cima Nikita"]),
        _entry("2026-07-02", ["Cima Nikita"]),
    ]
    e = canonicalize_route_names(_entry("2026-07-03", ["CIMA NIKITA"]), history)
    assert e["routes"][0]["name"] == "Cima Nikita"


def test_other_crag_and_different_names_are_left_alone():
    history = [_entry("2026-07-01", ["Cima Nikita"], spot="Kronthal"), _entry("2026-07-02", ["Judd"])]
    e = canonicalize_route_names(_entry("2026-07-03", ["cima nikita", "Jude"]), history)
    # different crag → only trimmed; "Jude" vs "Judd" is a judgement, not a typo
    assert [r["name"] for r in e["routes"]] == ["cima nikita", "Jude"]


def test_append_and_update_store_the_canonical_name(tmp_log_dir):
    append_outdoor_session(_entry("2026-07-01", ["Cima Nikita"]), None)
    append_outdoor_session(_entry("2026-07-02", ["cima nikita "]), None)
    update_outdoor_session(None, "2026-07-02", _entry("2026-07-02", ["CIMA nikita", "Heinz"]))
    names = {r["name"] for s in load_outdoor_sessions(None) for r in s["routes"]}
    assert names == {"Cima Nikita", "Heinz"}
