"""B315 — nothing the coach can read may name the team or narrate internals.

The D266 re-run caught the coach telling a user, in a normal answer about
training drills, which person physically owned a book and that its ingestion
was "pending". That text came straight from a `v1.0 coverage gap` note in the
KB: the note exists so the coach knows the limits of its own knowledge, not so
it can recite them. Every file here ships inside the system prompt, so a name
or a process detail written anywhere in the KB is one the model may repeat.
"""

import re
from pathlib import Path

import pytest

KB = Path(__file__).resolve().parents[1] / "coach" / "knowledge"
KB_FILES = sorted(KB.rglob("*.md"))

# Real first names of people behind the app. A user must never see these.
TEAM_NAMES = ("Daniele", "Somensi")

# Phrases that narrate how the knowledge base gets built rather than what it
# knows. The KB may say a topic is absent; it may not say who holds the book,
# who is transcribing it, or when that will happen.
PROCESS_PHRASES = (
    "photo extraction",
    "owns the physical",
    "physical sources",
    "extraction pending",
    "not yet acquired",
)


def test_kb_never_names_the_team():
    offenders = [
        f"{p.relative_to(KB)}: {name}"
        for p in KB_FILES
        for name in TEAM_NAMES
        if re.search(rf"\b{name}\b", p.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        "the coach can read these files verbatim — team names must not appear: "
        + "; ".join(offenders)
    )


@pytest.mark.parametrize("phrase", PROCESS_PHRASES)
def test_kb_does_not_narrate_its_own_ingestion(phrase):
    offenders = [
        str(p.relative_to(KB))
        for p in KB_FILES
        if phrase.lower() in p.read_text(encoding="utf-8").lower()
    ]
    assert not offenders, (
        f"internal-process wording {phrase!r} is readable by the coach in: "
        + ", ".join(offenders)
        + " — state that the topic isn't in the engine yet, nothing more"
    )


def test_l1_carries_the_fourth_wall_rule():
    # The data fix above removes today's leaks; this rule is what stops the
    # model from inventing tomorrow's out of any status note that survives.
    l1 = (KB / "L1_coach_voice.md").read_text(encoding="utf-8")
    assert "fourth wall" in l1.lower()
    assert "isn't in the engine yet" in l1


def test_kb_does_not_deny_the_bechtel_drills_it_ships():
    """C264 — the KB claimed the Bechtel drills weren't integrated months after
    they were (23 `tech_*` exercises, C240/C255/C256), and the coach repeated
    that to a user. A stale gap note is worse than no note: it makes the coach
    deny a feature that exists."""
    import json

    catalog = Path(__file__).resolve().parents[1] / "catalog" / "exercises" / "v1" / "exercises.json"
    data = json.loads(catalog.read_text(encoding="utf-8"))
    items = data["exercises"] if isinstance(data, dict) else data
    key = "id" if "id" in items[0] else "exercise_id"
    shipped = {e[key] for e in items if str(e[key]).startswith("tech_")}
    assert shipped, "no tech_* drills in the catalog — has the id prefix changed?"

    kb = (KB / "L3" / "06_technique_movement.md").read_text(encoding="utf-8")
    assert "IS integrated" in kb, "the KB must state that the Bechtel set ships"
    # A sample of ids must be nameable by the coach, or it cannot answer "which
    # drills do I have?" even while knowing they exist.
    for probe in ("tech_pogo", "tech_hips_first", "tech_silent" if "tech_silent" in shipped else "tech_the_bump"):
        if probe in shipped:
            assert probe in kb, f"{probe} ships but is not listed in the KB drill catalog"
