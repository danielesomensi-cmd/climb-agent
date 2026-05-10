"""Sentinel tests for scripts/sync_status.py regex patterns.

If these tests fail, sync_status.py has stopped matching the documented
sentence structure of CLAUDE.md / PROJECT_BRIEF.md / README.md /
vocabulary_v1.md. See B-SYNC-FIX.

Snapshots live in backend/tests/fixtures/sync_snapshots/. Update them ONLY
when the sentence structure in the live docs intentionally changes — never
to chase counter drift. The sentinel guards structure, not values.

## Manual negative-test procedure (repeatable)

Run this once after any change to the regex patterns to confirm the sentinel
actually catches a broken pattern. NEVER commit the broken state.

    1. Open scripts/sync_status.py
    2. Corrupt one regex constant: e.g. change ENDPOINT_HEADER_REGEX so the
       literal "stripe webhook" becomes "stripe-webhook" (with a dash).
    3. Run: python -m pytest backend/tests/test_sync_status_sentinel.py -q
       Expected: at least one test FAILS with a message naming the regex.
    4. Restore: git checkout scripts/sync_status.py
    5. Re-run pytest: all sentinel tests must pass again.

If step 3 does NOT fail, the sentinel is broken — investigate before merging.
"""

import re
import sys
from pathlib import Path

import pytest

# Make scripts/ importable so we can pull the regex constants directly
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sync_status import (  # noqa: E402  (sys.path setup above)
    ENDPOINT_HEADER_REGEX,
    ENDPOINT_TABLE_ROW_REGEX,
    ENDPOINT_TOTAL_PARSE_REGEX,
    PAGES_HEADER_REGEX,
    ROUTER_HEADER_REGEX,
    VOCAB_CANONICAL_ENTRY_REGEX,
    VOCAB_CANONICAL_SECTION_REGEX,
    parse_vocab_canonical_list,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sync_snapshots"


@pytest.fixture(scope="module")
def claude_snapshot() -> str:
    return (FIXTURE_DIR / "CLAUDE.md.snapshot").read_text()


@pytest.fixture(scope="module")
def brief_snapshot() -> str:
    return (FIXTURE_DIR / "PROJECT_BRIEF.md.snapshot").read_text()


@pytest.fixture(scope="module")
def readme_snapshot() -> str:
    return (FIXTURE_DIR / "README.md.snapshot").read_text()


@pytest.fixture(scope="module")
def vocab_snapshot() -> str:
    return (FIXTURE_DIR / "vocabulary_v1.md.snapshot").read_text()


def test_endpoint_header_regex_matches_claude(claude_snapshot):
    assert re.search(ENDPOINT_HEADER_REGEX, claude_snapshot), (
        "ENDPOINT_HEADER_REGEX no longer matches CLAUDE.md. If the endpoint "
        "header sentence was restructured, update both the regex in "
        "sync_status.py and the fixture. See B-SYNC-FIX."
    )


def test_router_header_regex_matches_claude(claude_snapshot):
    assert re.search(ROUTER_HEADER_REGEX, claude_snapshot), (
        "ROUTER_HEADER_REGEX no longer matches CLAUDE.md. See B-SYNC-FIX."
    )


def test_pages_header_regex_matches_claude(claude_snapshot):
    assert re.search(PAGES_HEADER_REGEX, claude_snapshot), (
        "PAGES_HEADER_REGEX no longer matches CLAUDE.md. See B-SYNC-FIX."
    )


def test_endpoint_total_parse_regex_matches_claude(claude_snapshot):
    assert re.search(ENDPOINT_TOTAL_PARSE_REGEX, claude_snapshot), (
        "ENDPOINT_TOTAL_PARSE_REGEX no longer matches CLAUDE.md. "
        "See B-SYNC-FIX."
    )


def test_endpoint_table_rows_present_in_claude(claude_snapshot):
    rows = re.findall(ENDPOINT_TABLE_ROW_REGEX, claude_snapshot, re.MULTILINE)
    assert len(rows) > 0, (
        "ENDPOINT_TABLE_ROW_REGEX found zero rows in CLAUDE.md. "
        "See B-SYNC-FIX."
    )


def test_status_table_markers_present_brief(brief_snapshot):
    assert "<!-- STATUS_TABLE_START -->" in brief_snapshot
    assert "<!-- STATUS_TABLE_END -->" in brief_snapshot


def test_status_table_markers_present_readme(readme_snapshot):
    assert "<!-- STATUS_TABLE_START -->" in readme_snapshot
    assert "<!-- STATUS_TABLE_END -->" in readme_snapshot


def test_vocab_canonical_section_regex_matches_vocab(vocab_snapshot):
    """The section anchor must find both 'session' and 'module' canonical lists."""
    matches = re.findall(VOCAB_CANONICAL_SECTION_REGEX, vocab_snapshot, re.MULTILINE)
    assert "session" in matches and "module" in matches, (
        f"VOCAB_CANONICAL_SECTION_REGEX expected to match both 'session' and "
        f"'module' canonical headers in vocabulary_v1.md, got: {matches}. "
        f"See B-SYNC-FIX."
    )


def test_vocab_canonical_entry_regex_extracts_ids(vocab_snapshot):
    """End-to-end: parse_vocab_canonical_list must return non-empty lists."""
    sessions = parse_vocab_canonical_list(vocab_snapshot, "session")
    modules = parse_vocab_canonical_list(vocab_snapshot, "module")
    assert len(sessions) > 0, (
        "parse_vocab_canonical_list('session') returned empty list. "
        "VOCAB_CANONICAL_SECTION_REGEX or VOCAB_CANONICAL_ENTRY_REGEX broken. "
        "See B-SYNC-FIX."
    )
    assert len(modules) > 0, (
        "parse_vocab_canonical_list('module') returned empty list. "
        "VOCAB_CANONICAL_SECTION_REGEX or VOCAB_CANONICAL_ENTRY_REGEX broken. "
        "See B-SYNC-FIX."
    )
