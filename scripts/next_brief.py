#!/usr/bin/env python3
"""Print the next free brief number for each type (A/B/C/D).

Scans BOTH sources of truth:
  1. docs/ROADMAP_CURRENT.md — the canonical open/closed item list
  2. `git log --all` — commit messages that may reference briefs never
     added to the roadmap (historical label collisions, see lessons.md
     entry for 2026-04-06).

A brief number is considered "used" if it appears in EITHER source, so
the next free number is `max(used) + 1` across the union.

Usage:
    python scripts/next_brief.py            # all types
    python scripts/next_brief.py B          # only type B
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ROADMAP = REPO_ROOT / "docs" / "ROADMAP_CURRENT.md"

# Matches B189, A42, D168, C12 — not A-GTM-08, D-ROADMAP-XCHECK etc.
BRIEF_RE = re.compile(r"\b([ABCD])(\d+)(?![\w-])")


def scan_roadmap() -> set[tuple[str, int]]:
    if not ROADMAP.exists():
        return set()
    text = ROADMAP.read_text(encoding="utf-8")
    return {(t, int(n)) for t, n in BRIEF_RE.findall(text)}


def scan_git_log() -> set[tuple[str, int]]:
    try:
        out = subprocess.check_output(
            ["git", "log", "--all", "--pretty=%s%n%b"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return set()
    return {(t, int(n)) for t, n in BRIEF_RE.findall(out)}


def next_free(used: set[tuple[str, int]], kind: str) -> int:
    nums = [n for t, n in used if t == kind]
    return (max(nums) + 1) if nums else 1


def main() -> int:
    wanted = sys.argv[1:] or ["A", "B", "C", "D"]
    wanted = [w.upper() for w in wanted]
    for w in wanted:
        if w not in {"A", "B", "C", "D"}:
            print(f"unknown type: {w} (expected A/B/C/D)", file=sys.stderr)
            return 2

    roadmap_ids = scan_roadmap()
    git_ids = scan_git_log()
    used = roadmap_ids | git_ids

    print("Next free brief numbers (checked roadmap + git log):")
    for kind in wanted:
        n = next_free(used, kind)
        highest = max((x for t, x in used if t == kind), default=0)
        source_bits = []
        if (kind, highest) in roadmap_ids:
            source_bits.append("roadmap")
        if (kind, highest) in git_ids:
            source_bits.append("git")
        src = f" (highest {kind}{highest} in: {', '.join(source_bits)})" if highest else ""
        print(f"  {kind}{n}{src}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
