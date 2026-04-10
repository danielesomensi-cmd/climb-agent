"""Tests for scripts/trim_roadmap.py — ✅-based detection."""

import textwrap
from pathlib import Path

import pytest

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
from trim_roadmap import trim_roadmap, is_completed_table_row, is_header_or_separator


# ── Helpers ──────────────────────────────────────────────────────────────

def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


# ── Test data ────────────────────────────────────────────────────────────

SAMPLE_ROADMAP = """\
# Roadmap

## Priority 1 — Bugs

| ID | Title | Status |
|----|-------|--------|
| B1 | Fix crash | ✅ Done |
| B2 | Fix leak | ✅ Done |
| B3 | Open issue | WIP |

---

## Priority 2 — Features

- Some prose paragraph
- Another line

| ID | Title | Status |
|----|-------|--------|
| F1 | New feature | Planned |
"""

BULLET_ROADMAP = """\
# Roadmap

## Priority 1 — Bugs

- ✅ **B157** — Fixed the crash (2026-03-26)
- ✅ **B158** — Fixed the leak (2026-03-26)
- **B159** — Open bug, still WIP

---

## Priority 2 — Future

| ID | Title | Status |
|----|-------|--------|
| F1 | New feature | Planned |
"""

SUBSECTION_ROADMAP = """\
# Roadmap

## Priority 1.5 — Boulder

### A-B1 — Discipline selection

**Priority:** P1.5 | **Status:** ✅ Done | **Type:** A

Description of the feature.

### A-B2 — Open feature

**Priority:** P1.5 | **Status:** Open | **Type:** A

Still needs work.

---

## Priority 2 — Future

| ID | Title | Status |
|----|-------|--------|
| F1 | New feature | Planned |
"""

ALL_DONE_SECTION = """\
# Roadmap

## Priority 1 — Bugs

| ID | Title | Status |
|----|-------|--------|
| B1 | Fix crash | ✅ Done |
| B2 | Fix leak | ✅ Done |

---

## Priority 2 — Future

| ID | Title | Status |
|----|-------|--------|
| F1 | New feature | Planned |
"""

NO_COMPLETED = """\
# Roadmap

## Priority 1 — Bugs

| ID | Title | Status |
|----|-------|--------|
| B3 | Open issue | WIP |
"""

KEEP_SECTION_ROADMAP = """\
# Roadmap

## Completed phases (reference only)

| Phase | Completed |
|-------|-----------|
| 0: Catalog | 2026-02 |
| 1: Engine | 2026-02 |
"""


# ── Tests ────────────────────────────────────────────────────────────────

class TestDryRunNoChanges:
    def test_dry_run_does_not_modify_files(self, tmp_path):
        roadmap = _write(tmp_path, "ROADMAP.md", SAMPLE_ROADMAP)
        archive = tmp_path / "ARCHIVE.md"
        original = roadmap.read_text()

        summary = trim_roadmap(roadmap, archive, dry_run=True)

        assert summary["completed_count"] >= 2
        assert roadmap.read_text() == original
        assert not archive.exists()


class TestRemovesCompletedTableRows:
    def test_checkmark_rows_are_removed(self, tmp_path):
        roadmap = _write(tmp_path, "ROADMAP.md", SAMPLE_ROADMAP)
        archive = tmp_path / "ARCHIVE.md"

        trim_roadmap(roadmap, archive, dry_run=False)

        content = roadmap.read_text()
        assert "Fix crash" not in content
        assert "Fix leak" not in content


class TestRemovesCompletedBullets:
    def test_checkmark_bullets_are_removed(self, tmp_path):
        roadmap = _write(tmp_path, "ROADMAP.md", BULLET_ROADMAP)
        archive = tmp_path / "ARCHIVE.md"

        trim_roadmap(roadmap, archive, dry_run=False)

        content = roadmap.read_text()
        assert "B157" not in content
        assert "B158" not in content
        assert "B159" in content  # open item stays


class TestRemovesCompletedSubsections:
    def test_done_subsection_block_archived(self, tmp_path):
        roadmap = _write(tmp_path, "ROADMAP.md", SUBSECTION_ROADMAP)
        archive = tmp_path / "ARCHIVE.md"

        trim_roadmap(roadmap, archive, dry_run=False)

        content = roadmap.read_text()
        assert "A-B1" not in content  # completed block removed
        assert "A-B2" in content  # open block stays
        assert "Still needs work" in content


class TestPreservesOpenRows:
    def test_non_completed_rows_survive(self, tmp_path):
        roadmap = _write(tmp_path, "ROADMAP.md", SAMPLE_ROADMAP)
        archive = tmp_path / "ARCHIVE.md"

        trim_roadmap(roadmap, archive, dry_run=False)

        content = roadmap.read_text()
        assert "| B3 | Open issue | WIP |" in content
        assert "| F1 | New feature | Planned |" in content


class TestEmptySectionRemoved:
    def test_section_with_all_done_is_dropped(self, tmp_path):
        roadmap = _write(tmp_path, "ROADMAP.md", ALL_DONE_SECTION)
        archive = tmp_path / "ARCHIVE.md"

        trim_roadmap(roadmap, archive, dry_run=False)

        content = roadmap.read_text()
        # Empty section should be removed entirely
        assert "## Priority 1 — Bugs" not in content
        # But Priority 2 with open items should survive
        assert "## Priority 2 — Future" in content
        assert "| F1 | New feature | Planned |" in content


class TestArchivesToFile:
    def test_removed_rows_appear_in_archive(self, tmp_path):
        roadmap = _write(tmp_path, "ROADMAP.md", SAMPLE_ROADMAP)
        archive = tmp_path / "ARCHIVE.md"
        archive.write_text("# Archive\n", encoding="utf-8")

        trim_roadmap(roadmap, archive, dry_run=False)

        archive_content = archive.read_text()
        assert "Archived from ROADMAP_CURRENT.md" in archive_content
        assert "Fix crash" in archive_content
        assert "Fix leak" in archive_content

    def test_creates_archive_if_missing(self, tmp_path):
        roadmap = _write(tmp_path, "ROADMAP.md", SAMPLE_ROADMAP)
        archive = tmp_path / "NEW_ARCHIVE.md"

        trim_roadmap(roadmap, archive, dry_run=False)

        assert archive.exists()
        assert "Fix crash" in archive.read_text()


class TestKeepSection:
    def test_completed_phases_preserved(self, tmp_path):
        roadmap = _write(tmp_path, "ROADMAP.md", KEEP_SECTION_ROADMAP)
        archive = tmp_path / "ARCHIVE.md"

        trim_roadmap(roadmap, archive, dry_run=False)

        content = roadmap.read_text()
        assert "## Completed phases (reference only)" in content
        assert "0: Catalog" in content


class TestNonTableContentPreserved:
    def test_prose_paragraphs_untouched(self, tmp_path):
        roadmap = _write(tmp_path, "ROADMAP.md", SAMPLE_ROADMAP)
        archive = tmp_path / "ARCHIVE.md"

        trim_roadmap(roadmap, archive, dry_run=False)

        content = roadmap.read_text()
        assert "Some prose paragraph" in content
        assert "Another line" in content


class TestHandlesNoCompletedItems:
    def test_graceful_noop(self, tmp_path):
        roadmap = _write(tmp_path, "ROADMAP.md", NO_COMPLETED)
        archive = tmp_path / "ARCHIVE.md"
        original = roadmap.read_text()

        summary = trim_roadmap(roadmap, archive, dry_run=False)

        assert summary["completed_count"] == 0
        assert roadmap.read_text() == original
        assert not archive.exists()


class TestHelperFunctions:
    def test_completed_table_row(self):
        assert is_completed_table_row("| B1 | Fix crash | ✅ Done |")
        assert not is_completed_table_row("| B3 | Open issue | WIP |")
        assert not is_completed_table_row("| ID | Title | Status |")
        assert not is_completed_table_row("|------|--------|--------|")

    def test_header_or_separator(self):
        assert is_header_or_separator("| ID | Title | Status |")
        assert is_header_or_separator("|------|--------|--------|")
        assert not is_header_or_separator("| B1 | Fix crash | ✅ Done |")
