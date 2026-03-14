#!/usr/bin/env python3
"""Sync real project counters into PROJECT_BRIEF.md, CLAUDE.md, and README.md.

Usage:
    python scripts/sync_status.py

Reads counts from the codebase and updates:
  - PROJECT_BRIEF.md  (status table between markers)
  - README.md         (status table between markers)
  - CLAUDE.md         (endpoint total + router count inline)

Also runs validation checks and prints warnings for issues
that cannot be auto-fixed (e.g., missing template IDs in vocabulary).

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
README_PATH = os.path.join(REPO_ROOT, "README.md")
CLAUDE_PATH = os.path.join(REPO_ROOT, "CLAUDE.md")
VOCAB_PATH = os.path.join(REPO_ROOT, "docs", "vocabulary_v1.md")

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


def count_routers() -> int:
    """Count .py files in routers/ excluding __init__."""
    router_dir = os.path.join(REPO_ROOT, "backend/api/routers")
    return len([f for f in glob.glob(os.path.join(router_dir, "*.py"))
                if "__init__" not in f and "__pycache__" not in f])


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


# ── File updates ───────────────────────────────────────────────────

def parse_old_counts(text: str) -> dict[str, int]:
    """Extract existing counts from the status table."""
    old = {}
    for m in re.finditer(r"\|\s*(.+?)\s*\|\s*(\d+)\s*\|", text):
        label = m.group(1).strip()
        if label not in ("Metric", "--------", "--------|-------"):
            old[label] = int(m.group(2))
    return old


def update_marker_file(path: str, counts: list[tuple[str, int]], label: str) -> bool:
    """Update a file that uses STATUS_TABLE_START/END markers."""
    if not os.path.exists(path):
        return False

    with open(path) as f:
        content = f.read()

    if START_MARKER not in content or END_MARKER not in content:
        return False

    old_counts = parse_old_counts(content)
    new_table = build_table(counts)

    pattern = re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER)
    updated = re.sub(pattern, new_table, content, flags=re.DOTALL)

    if updated == content:
        print(f"  {label}: (no changes)")
        return True

    with open(path, "w") as f:
        f.write(updated)

    for name, value in counts:
        old_val = old_counts.get(name)
        if old_val is None:
            print(f"  {label}: + {name}: {value} (new)")
        elif old_val != value:
            print(f"  {label}: ~ {name}: {old_val} -> {value}")

    return True


def update_claude(endpoints: int, routers: int) -> bool:
    """Update inline counts in CLAUDE.md."""
    if not os.path.exists(CLAUDE_PATH):
        return False

    with open(CLAUDE_PATH) as f:
        content = f.read()

    original = content

    # Update endpoint total: "N endpoints total (M router + 1 app-level health check)"
    content = re.sub(
        r"\d+ endpoints total \(\d+ router \+ 1 app-level health check\)",
        f"{endpoints} endpoints total ({endpoints - 1} router + 1 app-level health check)",
        content,
    )

    # Update router count in repo structure: "# FastAPI REST API (N routers)"
    content = re.sub(
        r"# FastAPI REST API \(\d+ routers\)",
        f"# FastAPI REST API ({routers} routers)",
        content,
    )

    if content == original:
        print("  CLAUDE.md: (no changes)")
        return True

    with open(CLAUDE_PATH, "w") as f:
        f.write(content)

    print("  CLAUDE.md: updated endpoint/router counts")
    return True


# ── Validation ─────────────────────────────────────────────────────

def validate(endpoints: int) -> list[str]:
    """Run validation checks and return warnings."""
    warnings = []

    # Check template list in vocabulary matches filesystem
    template_files = sorted([
        os.path.splitext(os.path.basename(f))[0]
        for f in glob.glob(os.path.join(REPO_ROOT, "backend/catalog/templates/v1/*.json"))
    ])
    if os.path.exists(VOCAB_PATH):
        with open(VOCAB_PATH) as f:
            vocab_content = f.read()
        for t in template_files:
            if f"- `{t}`" not in vocab_content:
                warnings.append(
                    f"vocabulary_v1.md: template '{t}' exists on disk but not in canonical list"
                )

    # Check CLAUDE.md endpoint table row count matches declared total
    if os.path.exists(CLAUDE_PATH):
        with open(CLAUDE_PATH) as f:
            claude = f.read()
        table_rows = len(re.findall(
            r"^\| (GET|POST|PUT|DELETE|PATCH) ", claude, re.MULTILINE
        ))
        declared = re.search(r"(\d+) endpoints? total", claude)
        if declared and table_rows != int(declared.group(1)):
            warnings.append(
                f"CLAUDE.md: endpoint table has {table_rows} rows "
                f"but header declares {declared.group(1)}"
            )

    return warnings


# ── Main ────────────────────────────────────────────────────────────

def main() -> int:
    print("Collecting counts...")
    counts = collect_counts()
    endpoints = dict(counts)["API endpoints"]
    routers = count_routers()

    for label, value in counts:
        print(f"  {label}: {value}")
    print(f"  Routers: {routers}")

    print()
    print("Syncing files...")
    update_marker_file(BRIEF_PATH, counts, "PROJECT_BRIEF.md")
    update_marker_file(README_PATH, counts, "README.md")
    update_claude(endpoints, routers)

    print()
    warnings = validate(endpoints)
    if warnings:
        for w in warnings:
            print(f"  \u26a0\ufe0f  {w}")
    else:
        print("  \u2705 All validations passed.")

    print()
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

    # Optional: trim completed roadmap items
    # Uncomment to auto-trim on every sync:
    # import subprocess
    # subprocess.run([sys.executable, str(Path(__file__).parent / "trim_roadmap.py")], check=True)
