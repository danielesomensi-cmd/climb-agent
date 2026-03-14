#!/usr/bin/env python3
"""Trim completed items from ROADMAP_CURRENT.md and archive them.

Usage:
    python scripts/trim_roadmap.py [--dry-run] [--archive-to FILE]

Completed rows (containing ~~strikethrough~~ in ID or Title cell) are removed
from ROADMAP_CURRENT.md. Empty sections get a placeholder. Removed rows are
appended to the archive file with a dated header.
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROADMAP = REPO_ROOT / "docs" / "ROADMAP_CURRENT.md"
DEFAULT_ARCHIVE = REPO_ROOT / "docs" / "ROADMAP_v2.md"

# Table header patterns to skip (never treat as completed)
HEADER_PATTERNS = re.compile(
    r"^\|\s*("
    r"ID|Title|Effort|Notes|#|Area|Dettaglio|Step|Method|Path|Description"
    r"|Theme|Detail|Origin|Phase|Completed|Highlights|Metric|Test result"
    r"|Current use|New use|Impact"
    r")\s*\|",
    re.IGNORECASE,
)
SEPARATOR_RE = re.compile(r"^\|[\s\-:|]+\|")
SECTION_RE = re.compile(r"^## .+")
COMPLETED_RE = re.compile(r"^\|[^|]*~~[^|]*\|")


def is_table_row(line: str) -> bool:
    """Return True if line is a markdown table row."""
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 3


def is_header_or_separator(line: str) -> bool:
    """Return True if line is a table header or separator row."""
    stripped = line.strip()
    return bool(HEADER_PATTERNS.match(stripped) or SEPARATOR_RE.match(stripped))


def is_completed_row(line: str) -> bool:
    """Return True if table row has strikethrough in ID or Title cell."""
    if not is_table_row(line) or is_header_or_separator(line):
        return False
    return bool(COMPLETED_RE.match(line.strip()))


def trim_roadmap(
    roadmap_path: Path = DEFAULT_ROADMAP,
    archive_path: Path = DEFAULT_ARCHIVE,
    dry_run: bool = False,
) -> dict:
    """Trim completed rows from roadmap, archive them.

    Returns a summary dict with counts and sizes.
    """
    content = roadmap_path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    original_size = len(content.encode("utf-8"))

    completed_rows: list[str] = []
    output_lines: list[str] = []

    # Track sections for empty-section collapse
    current_section_header_idx: int | None = None
    section_has_open_rows = False
    section_has_table = False
    table_header_lines: list[tuple[int, str]] = []  # (output_idx, line)

    def _collapse_empty_section():
        """If current section's table has no open rows, replace with placeholder."""
        nonlocal section_has_open_rows, section_has_table, table_header_lines
        if (
            current_section_header_idx is not None
            and section_has_table
            and not section_has_open_rows
            and table_header_lines
        ):
            # Remove table header/separator lines
            indices_to_remove = sorted([idx for idx, _ in table_header_lines], reverse=True)
            for idx in indices_to_remove:
                if idx < len(output_lines):
                    output_lines.pop(idx)
            # Add placeholder after section header
            # Find where section header is in output_lines
            for i, line in enumerate(output_lines):
                if line.strip().startswith("## ") and i >= (current_section_header_idx - 5 if current_section_header_idx else 0):
                    # Check if next non-empty line is our description or nothing
                    break
            output_lines.append("\nAll items completed.\n")

    for line in lines:
        stripped = line.strip()

        # Detect section boundaries
        if SECTION_RE.match(stripped):
            _collapse_empty_section()
            current_section_header_idx = len(output_lines)
            section_has_open_rows = False
            section_has_table = False
            table_header_lines = []
            output_lines.append(line)
            continue

        # Process table rows
        if is_table_row(line):
            if is_header_or_separator(line):
                section_has_table = True
                table_header_lines.append((len(output_lines), line))
                output_lines.append(line)
            elif is_completed_row(line):
                completed_rows.append(line)
            else:
                section_has_open_rows = True
                output_lines.append(line)
        else:
            output_lines.append(line)

    # Handle last section
    _collapse_empty_section()

    new_content = "".join(output_lines)
    new_size = len(new_content.encode("utf-8"))

    summary = {
        "completed_count": len(completed_rows),
        "original_size_kb": round(original_size / 1024, 1),
        "new_size_kb": round(new_size / 1024, 1),
        "savings_kb": round((original_size - new_size) / 1024, 1),
    }

    if dry_run:
        return summary

    if not completed_rows:
        return summary

    # Write trimmed roadmap
    roadmap_path.write_text(new_content, encoding="utf-8")

    # Append to archive
    archive_header = f"\n### Archived from ROADMAP_CURRENT.md — {date.today().isoformat()}\n\n"
    archive_block = archive_header + "".join(completed_rows) + "\n"

    if archive_path.exists():
        existing = archive_path.read_text(encoding="utf-8")
        archive_path.write_text(existing + archive_block, encoding="utf-8")
    else:
        archive_path.write_text(
            f"# Roadmap Archive\n\n{archive_block}", encoding="utf-8"
        )

    return summary


def main():
    parser = argparse.ArgumentParser(description="Trim completed items from ROADMAP_CURRENT.md")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no file changes")
    parser.add_argument(
        "--archive-to",
        type=Path,
        default=DEFAULT_ARCHIVE,
        help=f"Archive file (default: {DEFAULT_ARCHIVE.relative_to(REPO_ROOT)})",
    )
    args = parser.parse_args()

    roadmap = DEFAULT_ROADMAP
    if not roadmap.exists():
        print(f"Error: {roadmap} not found", file=sys.stderr)
        sys.exit(1)

    summary = trim_roadmap(
        roadmap_path=roadmap,
        archive_path=args.archive_to,
        dry_run=args.dry_run,
    )

    mode = "DRY RUN" if args.dry_run else "DONE"
    print(f"[{mode}] Archived {summary['completed_count']} items, "
          f"ROADMAP {summary['original_size_kb']} KB → {summary['new_size_kb']} KB "
          f"(saved {summary['savings_kb']} KB)")


if __name__ == "__main__":
    main()
