"""Tests for scripts/trim_roadmap.py."""

import textwrap
from pathlib import Path

import pytest

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
from trim_roadmap import trim_roadmap, is_completed_row, is_header_or_separator


# ── Helpers ──────────────────────────────────────────────────────────────

def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


SAMPLE_ROADMAP = """\
# Roadmap

## Priority 1 — Bugs

| ID | Title | Notes |
|----|-------|-------|
| ~~B1~~ | ~~Fix crash~~ | Done |
| ~~B2~~ | ~~Fix leak~~ | Done |
| B3 | Open issue | WIP |

---

## Priority 2 — Future

- Some prose paragraph
- Another line

| ID | Title | Notes |
|----|-------|-------|
| F1 | New feature | Planned |
"""

ALL_DONE_ROADMAP = """\
# Roadmap

## Priority 1 — Bugs

| ID | Title | Notes |
|----|-------|-------|
| ~~B1~~ | ~~Fix crash~~ | Done |
| ~~B2~~ | ~~Fix leak~~ | Done |

---

## Priority 2 — Future

| ID | Title | Notes |
|----|-------|-------|
| F1 | New feature | Planned |
"""

NO_COMPLETED_ROADMAP = """\
# Roadmap

## Priority 1 — Bugs

| ID | Title | Notes |
|----|-------|-------|
| B3 | Open issue | WIP |
"""


# ── Tests ────────────────────────────────────────────────────────────────

class TestDryRunNoChanges:
    def test_dry_run_does_not_modify_files(self, tmp_path):
        roadmap = _write(tmp_path, "ROADMAP.md", SAMPLE_ROADMAP)
        archive = tmp_path / "ARCHIVE.md"
        original = roadmap.read_text()

        summary = trim_roadmap(roadmap, archive, dry_run=True)

        assert summary["completed_count"] == 2
        assert roadmap.read_text() == original
        assert not archive.exists()


class TestRemovesCompletedRows:
    def test_strikethrough_rows_are_removed(self, tmp_path):
        roadmap = _write(tmp_path, "ROADMAP.md", SAMPLE_ROADMAP)
        archive = tmp_path / "ARCHIVE.md"

        summary = trim_roadmap(roadmap, archive, dry_run=False)

        assert summary["completed_count"] == 2
        content = roadmap.read_text()
        assert "~~B1~~" not in content
        assert "~~B2~~" not in content


class TestPreservesOpenRows:
    def test_non_strikethrough_rows_survive(self, tmp_path):
        roadmap = _write(tmp_path, "ROADMAP.md", SAMPLE_ROADMAP)
        archive = tmp_path / "ARCHIVE.md"

        trim_roadmap(roadmap, archive, dry_run=False)

        content = roadmap.read_text()
        assert "| B3 | Open issue | WIP |" in content
        assert "| F1 | New feature | Planned |" in content


class TestPreservesSectionHeaders:
    def test_section_headers_never_removed(self, tmp_path):
        roadmap = _write(tmp_path, "ROADMAP.md", SAMPLE_ROADMAP)
        archive = tmp_path / "ARCHIVE.md"

        trim_roadmap(roadmap, archive, dry_run=False)

        content = roadmap.read_text()
        assert "## Priority 1 — Bugs" in content
        assert "## Priority 2 — Future" in content


class TestArchivesToFile:
    def test_removed_rows_appear_in_archive(self, tmp_path):
        roadmap = _write(tmp_path, "ROADMAP.md", SAMPLE_ROADMAP)
        archive = tmp_path / "ARCHIVE.md"
        archive.write_text("# Archive\n", encoding="utf-8")

        trim_roadmap(roadmap, archive, dry_run=False)

        archive_content = archive.read_text()
        assert "Archived from ROADMAP_CURRENT.md" in archive_content
        assert "~~B1~~" in archive_content
        assert "~~B2~~" in archive_content

    def test_creates_archive_if_missing(self, tmp_path):
        roadmap = _write(tmp_path, "ROADMAP.md", SAMPLE_ROADMAP)
        archive = tmp_path / "NEW_ARCHIVE.md"

        trim_roadmap(roadmap, archive, dry_run=False)

        assert archive.exists()
        assert "~~B1~~" in archive.read_text()


class TestEmptySectionCollapses:
    def test_section_with_all_done_gets_placeholder(self, tmp_path):
        roadmap = _write(tmp_path, "ROADMAP.md", ALL_DONE_ROADMAP)
        archive = tmp_path / "ARCHIVE.md"

        trim_roadmap(roadmap, archive, dry_run=False)

        content = roadmap.read_text()
        assert "## Priority 1 — Bugs" in content
        assert "All items completed." in content
        # Table headers should be removed from the empty section
        # But F1 should still be there
        assert "| F1 | New feature | Planned |" in content


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
        roadmap = _write(tmp_path, "ROADMAP.md", NO_COMPLETED_ROADMAP)
        archive = tmp_path / "ARCHIVE.md"
        original = roadmap.read_text()

        summary = trim_roadmap(roadmap, archive, dry_run=False)

        assert summary["completed_count"] == 0
        assert roadmap.read_text() == original
        assert not archive.exists()
