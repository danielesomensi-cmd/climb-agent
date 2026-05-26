"""Coach KB keyword router.

Parses `backend/coach/knowledge/_index.md` at module import time, then exposes
`route_query(query, max_files=3)` which returns the L3 file paths most relevant
to the query, ranked by keyword-match count.

Algorithm (BM25-style, no embeddings — sufficient for v1.0):
  1. Lowercase + tokenize the query (alphanumerics + simple multi-word phrases
     for keywords containing spaces, like "no hangboard").
  2. For each L3 row in the index, count distinct keywords matched (any
     occurrence counts as +1; multiple occurrences of the same keyword count
     once).
  3. Rank by score desc; ties broken by row order in `_index.md`.
  4. Cap at `max_files`. If zero match: return the documented fallback pair
     (`L3/01_periodization.md` + `L3/15_goal_setting_motivation.md`).
  5. Co-load rule: if `10_injuries_fingers` routes AND the query contains any
     keyword from `02_finger_strength`, ensure `02_finger_strength` is also
     included (subject to the cap).

Out of scope for v1.0: embedding/semantic search, query reformulation,
cross-reference graph traversal (see `docs/coach/design.md` §9).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
INDEX_PATH = KNOWLEDGE_DIR / "_index.md"

FALLBACK_FILES = (
    KNOWLEDGE_DIR / "L3" / "01_periodization.md",
    KNOWLEDGE_DIR / "L3" / "15_goal_setting_motivation.md",
)

CO_LOAD_TRIGGER = "10_injuries_fingers.md"
CO_LOAD_TARGET = "02_finger_strength.md"

_KEYWORD_LINE_RE = re.compile(
    r"^\|\s*(?P<keywords>[^|]+?)\s*\|\s*`(?P<path>L3/[^`]+\.md)`"
)
_QUOTED_KEYWORD_RE = re.compile(r'"([^"]+)"')
_WORD_TOKEN_RE = re.compile(r"[a-z0-9+×x]+")


@dataclass(frozen=True)
class RoutingRow:
    """One row of the L3 keyword routing table."""

    path: Path
    keywords: tuple[str, ...]
    multi_word_keywords: tuple[str, ...] = field(default=())


@lru_cache(maxsize=1)
def _load_routing_table() -> tuple[RoutingRow, ...]:
    """Parse _index.md once and cache the routing rows in source order."""
    if not INDEX_PATH.exists():
        logger.error("Routing index not found at %s", INDEX_PATH)
        return ()

    rows: list[RoutingRow] = []
    try:
        text = INDEX_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        logger.error("Could not read routing index: %s", exc)
        return ()

    in_routing_section = False
    for line in text.splitlines():
        if line.startswith("## Keyword routing map"):
            in_routing_section = True
            continue
        if in_routing_section and line.startswith("## "):
            break
        if not in_routing_section:
            continue

        match = _KEYWORD_LINE_RE.match(line)
        if not match:
            continue

        keyword_field = match.group("keywords")
        path_field = match.group("path")

        raw_keywords = [
            kw.strip().lower() for kw in _QUOTED_KEYWORD_RE.findall(keyword_field)
        ]
        if not raw_keywords:
            continue

        single_word = tuple(kw for kw in raw_keywords if " " not in kw and "-" not in kw)
        multi_word = tuple(kw for kw in raw_keywords if " " in kw or "-" in kw)

        rows.append(
            RoutingRow(
                path=KNOWLEDGE_DIR / path_field,
                keywords=single_word,
                multi_word_keywords=multi_word,
            )
        )

    return tuple(rows)


def _tokenize(query: str) -> set[str]:
    """Lowercase the query and return the set of word tokens."""
    return set(_WORD_TOKEN_RE.findall(query.lower()))


def _score_row(query_lower: str, query_tokens: set[str], row: RoutingRow) -> int:
    """Count distinct keywords matched in the query."""
    score = 0
    for kw in row.keywords:
        if kw in query_tokens:
            score += 1
    for kw in row.multi_word_keywords:
        if kw in query_lower:
            score += 1
    return score


def route_query(query: str, max_files: int = 3) -> list[Path]:
    """Route a user query to the most relevant L3 files.

    Args:
        query: Raw user message. Case-insensitive matching.
        max_files: Hard cap on returned paths (default 3, per audit §5).

    Returns:
        Ordered list of L3 file Paths, most relevant first. Length 0 to
        `max_files`. Returns the documented fallback pair when no keywords
        match. Returns [] only if the index itself is missing or unparseable.
    """
    if max_files <= 0:
        return []

    rows = _load_routing_table()
    if not rows:
        return []

    query_lower = query.lower()
    query_tokens = _tokenize(query)

    scored: list[tuple[int, int, RoutingRow]] = []
    for idx, row in enumerate(rows):
        score = _score_row(query_lower, query_tokens, row)
        if score > 0:
            scored.append((score, idx, row))

    if not scored:
        return [p for p in FALLBACK_FILES[:max_files]]

    scored.sort(key=lambda t: (-t[0], t[1]))
    selected = [t[2].path for t in scored[:max_files]]

    selected_names = {p.name for p in selected}
    if CO_LOAD_TRIGGER in selected_names and CO_LOAD_TARGET not in selected_names:
        finger_row = next(
            (r for r in rows if r.path.name == CO_LOAD_TARGET), None
        )
        if finger_row is not None and _score_row(query_lower, query_tokens, finger_row) > 0:
            if len(selected) >= max_files:
                selected = selected[:-1]
            selected.append(finger_row.path)

    return selected


def _clear_cache() -> None:
    """Reset the cached routing table — test-only helper."""
    _load_routing_table.cache_clear()
