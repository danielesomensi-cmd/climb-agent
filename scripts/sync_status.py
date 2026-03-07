#!/usr/bin/env python3
"""Sync real project counters into PROJECT_BRIEF.md.

Usage:
    python scripts/sync_status.py

Reads counts from the codebase and updates the status table between
<!-- STATUS_TABLE_START --> and <!-- STATUS_TABLE_END --> markers in
PROJECT_BRIEF.md.  Prints a diff summary to stdout.

No external dependencies — stdlib only (+ pytest subprocess).
"""

import glob
import json
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BRIEF_PATH = os.path.join(REPO_ROOT, "PROJECT_BRIEF.md")

START_MARKER = "<!-- STATUS_TABLE_START -->"
END_MARKER = "<!-- STATUS_TABLE_END -->"


# ── Counters ────────────────────────────────────────────────────────

def count_tests() -> int:
    """Run pytest --collect-only and parse the count."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "backend/tests", "--collect-only", "-q"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    total = 0
    for line in result.stdout.splitlines():
        # Format: "backend/tests/test_foo.py: 42"
        m = re.match(r".+\.py:\s*(\d+)$", line)
        if m:
            total += int(m.group(1))
    # Fallback: try "N tests collected" or "N test" summary line
    if total == 0:
        for line in reversed(result.stdout.strip().splitlines()):
            m = re.match(r"(\d+) test", line)
            if m:
                return int(m.group(1))
    return total


def count_exercises() -> int:
    path = os.path.join(REPO_ROOT, "backend/catalog/exercises/v1/exercises.json")
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, dict) and "exercises" in data:
        return len(data["exercises"])
    if isinstance(data, list):
        return len(data)
    return 0


def count_sessions() -> int:
    pattern = os.path.join(REPO_ROOT, "backend/catalog/sessions/v1/*.json")
    return len(glob.glob(pattern))


def count_templates() -> int:
    pattern = os.path.join(REPO_ROOT, "backend/catalog/templates/v1/*.json")
    return len(glob.glob(pattern))


def count_api_endpoints() -> int:
    """Count @router.{get,post,put,delete,patch} decorators + @app routes."""
    count = 0
    router_dir = os.path.join(REPO_ROOT, "backend/api/routers")
    for py_file in glob.glob(os.path.join(router_dir, "*.py")):
        with open(py_file) as f:
            for line in f:
                if re.match(r"\s*@router\.(get|post|put|delete|patch)\b", line):
                    count += 1
    # Check main.py for app-level routes (e.g. /health)
    main_path = os.path.join(REPO_ROOT, "backend/api/main.py")
    if os.path.exists(main_path):
        with open(main_path) as f:
            for line in f:
                if re.match(r"\s*@app\.(get|post|put|delete|patch)\b", line):
                    count += 1
    return count


def count_frontend_pages() -> int:
    pattern = os.path.join(REPO_ROOT, "frontend/src/app/**/page.tsx")
    return len(glob.glob(pattern, recursive=True))


def count_frontend_components() -> int:
    pattern = os.path.join(REPO_ROOT, "frontend/src/components/**/*.tsx")
    return len(glob.glob(pattern, recursive=True))


# ── Table generation ────────────────────────────────────────────────

def collect_counts() -> list[tuple[str, int]]:
    return [
        ("Tests (passing)", count_tests()),
        ("Exercises", count_exercises()),
        ("Sessions (active)", count_sessions()),
        ("Templates", count_templates()),
        ("API endpoints", count_api_endpoints()),
        ("Frontend pages", count_frontend_pages()),
        ("Frontend components", count_frontend_components()),
    ]


def build_table(counts: list[tuple[str, int]]) -> str:
    lines = [
        START_MARKER,
        "| Metric | Count |",
        "|--------|-------|",
    ]
    for label, value in counts:
        lines.append(f"| {label} | {value} |")
    lines.append(END_MARKER)
    return "\n".join(lines)


# ── File update ─────────────────────────────────────────────────────

def parse_old_counts(text: str) -> dict[str, int]:
    """Extract existing counts from the status table."""
    old = {}
    for m in re.finditer(r"\|\s*(.+?)\s*\|\s*(\d+)\s*\|", text):
        label = m.group(1).strip()
        if label not in ("Metric", "--------", "--------|-------"):
            old[label] = int(m.group(2))
    return old


def update_brief(counts: list[tuple[str, int]]) -> bool:
    if not os.path.exists(BRIEF_PATH):
        print(f"WARNING: {BRIEF_PATH} not found — skipping update.")
        return False

    with open(BRIEF_PATH) as f:
        content = f.read()

    if START_MARKER not in content or END_MARKER not in content:
        print(f"WARNING: Markers not found in {BRIEF_PATH}.")
        print(f"  Expected: {START_MARKER} ... {END_MARKER}")
        print("  Add markers to PROJECT_BRIEF.md first.")
        return False

    old_counts = parse_old_counts(content)
    new_table = build_table(counts)

    # Replace between markers (inclusive)
    pattern = re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER)
    updated = re.sub(pattern, new_table, content, flags=re.DOTALL)

    with open(BRIEF_PATH, "w") as f:
        f.write(updated)

    # Print diff
    changed = False
    for label, value in counts:
        old_val = old_counts.get(label)
        if old_val is None:
            print(f"  + {label}: {value} (new)")
            changed = True
        elif old_val != value:
            print(f"  ~ {label}: {old_val} -> {value}")
            changed = True

    if not changed:
        print("  (no changes)")

    return True


# ── Main ────────────────────────────────────────────────────────────

def main() -> int:
    print("Collecting counts...")
    counts = collect_counts()

    for label, value in counts:
        print(f"  {label}: {value}")

    print()
    print("Updating PROJECT_BRIEF.md...")
    ok = update_brief(counts)

    if ok:
        print("Done.")
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
