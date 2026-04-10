#!/usr/bin/env python3
"""Trim completed items from ROADMAP_CURRENT.md and archive them.

Usage:
    python scripts/trim_roadmap.py [--dry-run] [--archive-to FILE]

Detection rules (✅-based):
- Bullet item: line starts with `- ✅` → archive the line
- Table row: data row (not header/separator) containing `✅` → archive
- Subsection block (###): title has ✅, Status field says ✅, or title
  starts with "### Completed" → archive entire block up to next ###/##
- Whole section (##): if no open items remain after filtering → archive

Preserved regardless:
- "Completed phases (reference only)" section (compact reference table)
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROADMAP = REPO_ROOT / "docs" / "ROADMAP_CURRENT.md"
DEFAULT_ARCHIVE = REPO_ROOT / "docs" / "ROADMAP_v2.md"

# Patterns
SECTION_RE = re.compile(r"^## .+")
SUBSECTION_RE = re.compile(r"^### .+")
HEADER_PATTERNS = re.compile(
    r"^\|\s*("
    r"ID|Title|Effort|Notes|#|Area|Dettaglio|Step|Method|Path|Description"
    r"|Theme|Detail|Origin|Phase|Completed|Highlights|Metric|Test result"
    r"|Current use|New use|Impact|Session|Status|Implemented|Deferred"
    r"|Brief|Scope|Type|Date|Ch\.|File|Item|Book|Block"
    r")\s*\|",
    re.IGNORECASE,
)
SEPARATOR_RE = re.compile(r"^\|[\s\-:|]+\|")
BRIEF_ID_RE = re.compile(r"\b([ABCD])(\d+)(?![\w-])")

# Sections to never trim (even if all items look completed)
KEEP_SECTION_KEYWORDS = ["completed phases"]


def is_table_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.endswith("|") and s.count("|") >= 3


def is_header_or_separator(line: str) -> bool:
    s = line.strip()
    return bool(HEADER_PATTERNS.match(s) or SEPARATOR_RE.match(s))


def is_completed_table_row(line: str) -> bool:
    if not is_table_row(line) or is_header_or_separator(line):
        return False
    return "✅" in line


def is_completed_bullet(line: str) -> bool:
    return line.strip().startswith("- ✅")


def _is_completed_subsection(block: list[str]) -> bool:
    """Check if a ### block is fully completed."""
    if not block:
        return False
    title = block[0].strip()
    # ✅ in the title itself
    if "✅" in title:
        return True
    # "### Completed" convention (entire subsection is done items)
    if title.lower().startswith("### completed"):
        return True
    # Check first few content lines for **Status:** ✅
    for line in block[1:8]:
        s = line.strip()
        if s.startswith("**") and "status:" in s.lower() and "✅" in s:
            return True
        # Stop at next heading or table data
        if s.startswith("#"):
            break
    return False


def _should_keep_section(header: str) -> bool:
    """Check if a ## section must be preserved regardless of content."""
    lower = header.strip().lower()
    return any(kw in lower for kw in KEEP_SECTION_KEYWORDS)


def _collect_subsection(lines: list[str], start: int) -> int:
    """Return end index (exclusive) for a ### block starting at `start`."""
    end = start + 1
    while end < len(lines):
        s = lines[end].strip()
        if s.startswith("## ") or s.startswith("### "):
            break
        end += 1
    return end


def _has_open_items(lines: list[str]) -> bool:
    """Check if a list of lines contains any open (non-completed) items."""
    for line in lines:
        s = line.strip()
        # Open bullet (starts with - but NOT - ✅)
        if s.startswith("- ") and not s.startswith("- ✅"):
            return True
        # Open table data row (no ✅)
        if is_table_row(line) and not is_header_or_separator(line) and "✅" not in line:
            return True
        # Open subsection (### without ✅)
        if s.startswith("### ") and "✅" not in s:
            # Need deeper check — could have ✅ in Status line
            # but we can't easily do that here, so conservative: it's open
            return True
    return False


def _clean_orphan_table_headers(lines: list[str]) -> list[str]:
    """Remove table header+separator pairs with no data rows following."""
    result: list[str] = []
    i = 0
    while i < len(lines):
        # Detect: header row followed by separator row
        if (
            i + 1 < len(lines)
            and is_table_row(lines[i])
            and HEADER_PATTERNS.match(lines[i].strip())
            and SEPARATOR_RE.match(lines[i + 1].strip())
        ):
            # Peek past separator for data rows
            j = i + 2
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            has_data = (
                j < len(lines)
                and is_table_row(lines[j])
                and not is_header_or_separator(lines[j])
            )
            if has_data:
                result.append(lines[i])
                result.append(lines[i + 1])
                i += 2
            else:
                # Skip orphaned header + separator
                i += 2
        else:
            result.append(lines[i])
            i += 1
    return result


def _clean_empty_sections(lines: list[str]) -> list[str]:
    """Remove ## sections that have no remaining items.

    A section is 'empty' if between its ## header and the next ## (or EOF)
    there are no bullets (- ...), no table data rows, and no ### subsections.
    """
    # Find section boundaries
    boundaries: list[int] = []
    for i, line in enumerate(lines):
        if SECTION_RE.match(line.strip()):
            boundaries.append(i)
    boundaries.append(len(lines))

    result: list[str] = []
    for idx in range(len(boundaries) - 1):
        start = boundaries[idx]
        end = boundaries[idx + 1]
        section = lines[start:end]
        header = section[0].strip()

        # Always keep protected sections
        if _should_keep_section(header):
            result.extend(section)
            continue

        # Check for any remaining items
        has_items = False
        for sline in section[1:]:
            s = sline.strip()
            if s.startswith("### "):
                has_items = True
                break
            if s.startswith("- "):
                has_items = True
                break
            if is_table_row(sline) and not is_header_or_separator(sline):
                has_items = True
                break
        if has_items:
            result.extend(section)
        # else: section is empty → drop it

    # Handle any lines before the first ## section (preamble)
    if boundaries and boundaries[0] > 0:
        result = lines[: boundaries[0]] + result

    return result


def _collapse_blank_runs(lines: list[str]) -> list[str]:
    """Collapse runs of 3+ blank lines down to 2."""
    result: list[str] = []
    blank_count = 0
    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 2:
                result.append(line)
        else:
            blank_count = 0
            result.append(line)
    return result


def trim_roadmap(
    roadmap_path: Path = DEFAULT_ROADMAP,
    archive_path: Path = DEFAULT_ARCHIVE,
    dry_run: bool = False,
) -> dict:
    content = roadmap_path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    original_size = len(content.encode("utf-8"))

    archived: list[str] = []
    output: list[str] = []
    i = 0
    in_keep_section = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Track ## sections for KEEP list
        if SECTION_RE.match(stripped):
            in_keep_section = _should_keep_section(stripped)

        # Never trim KEEP sections
        if in_keep_section:
            output.append(line)
            i += 1
            continue

        # ### subsection block: collect and decide
        if SUBSECTION_RE.match(stripped):
            end = _collect_subsection(lines, i)
            block = lines[i:end]
            if _is_completed_subsection(block):
                archived.extend(block)
            else:
                # Mixed: filter items, but if nothing open remains, archive whole block
                kept: list[str] = []
                block_archived: list[str] = []
                has_open_items = False
                for bline in block:
                    if is_completed_bullet(bline) or is_completed_table_row(bline):
                        block_archived.append(bline)
                    else:
                        kept.append(bline)
                        s = bline.strip()
                        if (s.startswith("- ") and not s.startswith("- ✅")) or (
                            is_table_row(bline)
                            and not is_header_or_separator(bline)
                            and "✅" not in bline
                        ):
                            has_open_items = True
                if has_open_items or not block_archived:
                    # Has open items, or no completed items found → keep block
                    archived.extend(block_archived)
                    output.extend(kept)
                else:
                    # All items were completed → archive entire block
                    archived.extend(block)
            i = end
            continue

        # Standalone completed bullet
        if is_completed_bullet(line):
            archived.append(line)
            i += 1
            continue

        # Standalone completed table row
        if is_completed_table_row(line):
            archived.append(line)
            i += 1
            continue

        output.append(line)
        i += 1

    # Cleanup passes
    output = _clean_orphan_table_headers(output)
    output = _clean_empty_sections(output)
    output = _collapse_blank_runs(output)

    new_content = "".join(output)
    new_size = len(new_content.encode("utf-8"))

    # Extract brief IDs from archived lines for safety check
    removed_ids = set()
    for row in archived:
        removed_ids.update(BRIEF_ID_RE.findall(row))

    summary = {
        "completed_count": len(archived),
        "original_size_kb": round(original_size / 1024, 1),
        "new_size_kb": round(new_size / 1024, 1),
        "savings_kb": round((original_size - new_size) / 1024, 1),
        "original_lines": len(lines),
        "new_lines": len(output),
    }

    if dry_run:
        summary["removed_ids"] = sorted(removed_ids)
        return summary

    if not archived:
        return summary

    # Write trimmed roadmap
    roadmap_path.write_text(new_content, encoding="utf-8")

    # Append to archive
    archive_header = (
        f"\n### Archived from ROADMAP_CURRENT.md — {date.today().isoformat()}\n\n"
    )
    archive_block = archive_header + "".join(archived) + "\n"

    if archive_path.exists():
        existing = archive_path.read_text(encoding="utf-8")
        archive_path.write_text(existing + archive_block, encoding="utf-8")
    else:
        archive_path.write_text(
            f"# Roadmap Archive\n\n{archive_block}", encoding="utf-8"
        )

    # Safety: verify every removed ID is in the archive
    if removed_ids:
        archive_text = archive_path.read_text(encoding="utf-8")
        archive_ids = set(BRIEF_ID_RE.findall(archive_text))
        missing = sorted(removed_ids - archive_ids)
        if missing:
            tokens = [f"{t}{n}" for t, n in missing]
            print(
                f"WARNING: {len(missing)} IDs removed from CURRENT but NOT found in "
                f"{archive_path.name}: {', '.join(tokens)}",
                file=sys.stderr,
            )
            summary["warning_missing_in_archive"] = tokens

    summary["removed_ids"] = sorted(removed_ids)
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Trim completed items from ROADMAP_CURRENT.md"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Report only, no file changes"
    )
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
    print(
        f"[{mode}] Archived {summary['completed_count']} lines, "
        f"ROADMAP {summary['original_lines']} → {summary['new_lines']} lines "
        f"({summary['original_size_kb']} KB → {summary['new_size_kb']} KB, "
        f"saved {summary['savings_kb']} KB)"
    )


if __name__ == "__main__":
    main()
