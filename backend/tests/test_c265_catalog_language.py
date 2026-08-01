"""C265 — catalog content is English-only.

The catalog is data rendered verbatim to users whose UI chrome is English. Four
handstand entries added by D262, three test entries and eight session notes had
been authored in Italian and shipped that way; this guard is what makes the next
one fail in CI instead of on a user's phone.

Detection strategy — deliberately narrow, to stay useful instead of noisy:

* We look for **Italian function words** (articles, prepositions, pronouns,
  auxiliaries) that are not also English words. They are the highest-signal
  marker available: a sentence written in Italian cannot avoid them, and an
  English sentence essentially never contains them. Domain nouns alone would be
  weaker — "muro", "presa" — because a single one can slip into an otherwise
  English string as a proper noun.
* We deliberately do **not** flag accented characters. Legitimate catalog
  content carries them in proper nouns (Eva López, Antoine de Saint-Exupéry,
  Hörst), so that rule would need a whitelist that grows with every author cited
  — maintenance cost with no detection gain over the function-word rule.
* Ambiguous tokens shared with English ("per", "come", "tempo", "via", "non" as
  in "non-negotiable", "in", "a", "e") are excluded by construction. The false
  positives they produce would train us to ignore this test.

Scope is discovered, not hardcoded to a list of files: every JSON under the
catalog root is walked, so a new catalog package is covered on the day it lands.
"""
import json
import re
from pathlib import Path

import pytest

CATALOG_ROOT = Path("backend/catalog")

# Fields whose values reach the user's screen (or the coach's context).
TEXT_KEYS = {
    "name", "title", "label", "description", "notes", "note", "text",
    "benchmark_note", "source", "cues", "tips", "tip", "summary", "explanation",
    "nudge", "condition_note", "warmup_protocol_add", "stop_criteria",
    "skin_tips", "author", "instructions", "hint",
}

# Italian function words that are never ordinary English words.
ITALIAN_FUNCTION_WORDS = {
    "il", "lo", "gli", "della", "dello", "delle", "degli", "dei", "dal",
    "dalla", "dallo", "dai", "nel", "nella", "nello", "nei", "negli", "sul",
    "sulla", "sullo", "sui", "sulle", "col", "coi", "che", "chi", "più",
    "senza", "mentre", "quando", "perché", "quindi", "oppure", "questo",
    "questa", "questi", "quello", "quella", "sono", "essere", "avere",
    "viene", "vengono", "deve", "devi", "puoi", "possono", "sempre", "mai",
    "molto", "anche", "ancora", "tutti", "tutte", "tutto",
}

# High-signal Italian domain nouns/verbs seen in the catalog's own history.
ITALIAN_DOMAIN_WORDS = {
    "muro", "spalle", "braccia", "gamba", "gambe", "piedi", "ginocchia",
    "polsi", "dita", "mani", "petto", "schiena", "slancio", "equilibrio",
    "verticale", "serie", "ripetizione", "ripetizioni", "carico", "recupero",
    "esercizio", "allenamento", "mantenimento", "forza", "sospensioni",
    "riposo", "respira", "scendi", "stacca", "spingi", "mantieni",
    "appoggiate", "controllato", "seduta", "tentativi", "scarso",
    "intermedio", "avanzato", "empirici",
}

ITALIAN_WORDS = ITALIAN_FUNCTION_WORDS | ITALIAN_DOMAIN_WORDS

WORD_RE = re.compile(r"[a-zA-ZàèéìòùÀÈÉÌÒÙ]+")


def _iter_strings(node, path, key=None):
    """Yield (json_path, key, value) for every string in a decoded JSON tree."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _iter_strings(v, f"{path}.{k}", k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _iter_strings(v, f"{path}[{i}]", key)
    elif isinstance(node, str):
        yield path, key, node


def _italian_hits(value):
    words = {w.lower() for w in WORD_RE.findall(value)}
    return sorted(words & ITALIAN_WORDS)


def _catalog_files():
    files = sorted(CATALOG_ROOT.rglob("*.json"))
    assert files, f"no catalog JSON found under {CATALOG_ROOT} — wrong cwd?"
    return files


@pytest.mark.parametrize("path", _catalog_files(), ids=lambda p: str(p))
def test_catalog_user_facing_text_is_english(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    offenders = [
        (json_path, value, hits)
        for json_path, key, value in _iter_strings(data, "")
        if key in TEXT_KEYS and (hits := _italian_hits(value))
    ]
    assert not offenders, "Italian text in user-facing catalog fields:\n" + "\n".join(
        f"  {path}{jp}  {hits}\n    {value}" for jp, value, hits in offenders
    )


def test_guard_detects_italian():
    """The detector must actually fire — a guard that cannot fail guards nothing.

    Anchored on the real pre-C265 string, not a synthetic one (B317's lesson:
    a test written against invented data verifies the function, not the world).
    """
    pre_c265 = "Frena con gli addominali quando i piedi toccano il muro"
    assert _italian_hits(pre_c265)


def test_guard_does_not_fire_on_english():
    """Strings that tripped the drafting heuristics but are correct English."""
    for ok in (
        "Lower back pressed firmly into the floor for every single rep — non-negotiable",
        "Brake with the core as the heels touch the wall — do not slam into it",
        "Slow tempo: 2s uncurl, 2s re-curl",
        "4-5 reps, 7-10s work. Eva López IntHangs standard protocol.",
        "Antoine de Saint-Exupéry",
    ):
        assert not _italian_hits(ok), ok
