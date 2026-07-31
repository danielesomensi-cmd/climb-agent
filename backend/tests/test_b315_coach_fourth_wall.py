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
