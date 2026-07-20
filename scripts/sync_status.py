#!/usr/bin/env python3
"""Sync real project counters into PROJECT_BRIEF.md, CLAUDE.md, and README.md.

Usage:
    python scripts/sync_status.py

Reads counts from the codebase and updates:
  - PROJECT_BRIEF.md  (status table between markers)
  - README.md         (status table between markers)
  - CLAUDE.md         (endpoint total + router count + page count, inline)

Also runs validation checks and prints warnings for issues that cannot be
auto-fixed (e.g., missing template IDs in vocabulary, vocab→disk orphans,
CLAUDE.md endpoint header drift vs code).

No external dependencies — stdlib only (+ pytest subprocess).

## Sync limits — won't auto-update

The following content is INTENTIONALLY not auto-synced. Edit by hand as part
of the brief that introduces the change.

- Tech-stack tables (PROJECT_BRIEF.md tech stack section, ~lines 71-78)
- Pricing rows (ROADMAP_CURRENT.md Priority 4 / Future)
- GTM Sprint status callouts (ROADMAP_CURRENT.md Priority 1.75, ~lines 85-89)
- The CLAUDE.md endpoint TABLE rows (only the inline header gets auto-updated;
  the table rows must be edited manually when adding/removing endpoints)
- Any free-prose status assertion ("LIVE since YYYY-MM-DD", "TEST MODE",
  "temporarily disabled", etc.) anywhere in the doc tree

If a counter / status / table changes, update it in the same brief that
introduces the change. The sentinel test in
`backend/tests/test_sync_status_sentinel.py` guards the regex patterns'
structural match against snapshot fixtures of the source docs.
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


# ── Regex patterns (source of truth — sentinel-tested) ─────────────
# These patterns are imported by backend/tests/test_sync_status_sentinel.py
# to assert structural compatibility with the live docs. If a doc's wording
# changes intentionally, update both the pattern and the snapshot fixture.

ENDPOINT_HEADER_REGEX = (
    r"\d+ endpoints total "
    r"\(\d+ router \+ 2 app-level: health check \+ stripe webhook\)"
)
ROUTER_HEADER_REGEX = r"# FastAPI REST API \(\d+ routers\)"
PAGES_HEADER_REGEX = r"\*\*Pages \(\d+\):\*\*"
ENDPOINT_TOTAL_PARSE_REGEX = r"(\d+) endpoints? total"
ENDPOINT_TABLE_ROW_REGEX = r"^\| (GET|POST|PUT|DELETE|PATCH) "
VOCAB_CANONICAL_SECTION_REGEX = (
    r"^#{2,4}\s+(?:[\d.]+\s+)?Canonical\s+(session|module)"
    r"\s+template_ids\s*\(\d+\)\s*$"
)
VOCAB_CANONICAL_ENTRY_REGEX = r"^-\s+`([a-zA-Z0-9_]+)`"


# ── Counters ────────────────────────────────────────────────────────

def count_tests() -> int:
    """Run pytest --collect-only and parse the count."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "backend/tests", "--collect-only", "-q"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    total = 0
    for line in result.stdout.splitlines():
        # Format: "backend/tests/test_foo.py: 42". Anchor on the test dir so
        # deprecation-warning lines that also end in ".py:<lineno>" (emitted on
        # stdout by some deps) are not mistaken for collection counts.
        m = re.match(r"backend/tests/\S+\.py:\s*(\d+)$", line)
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
    # Check main.py for app-level routes (decorators + add_api_route calls)
    main_path = os.path.join(REPO_ROOT, "backend/api/main.py")
    if os.path.exists(main_path):
        with open(main_path) as f:
            for line in f:
                if re.match(r"\s*@app\.(get|post|put|delete|patch)\b", line):
                    count += 1
                elif re.match(r"\s*app\.add_api_route\b", line):
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


def update_claude(endpoints: int, routers: int, pages: int) -> bool:
    """Update inline counts in CLAUDE.md (endpoints, routers, pages)."""
    if not os.path.exists(CLAUDE_PATH):
        return False

    with open(CLAUDE_PATH) as f:
        content = f.read()

    original = content

    # Endpoint header: "N endpoints total (M router + 2 app-level: health check + stripe webhook)"
    content = re.sub(
        ENDPOINT_HEADER_REGEX,
        f"{endpoints} endpoints total "
        f"({endpoints - 2} router + 2 app-level: health check + stripe webhook)",
        content,
    )

    # Router count in repo structure: "# FastAPI REST API (N routers)"
    content = re.sub(
        ROUTER_HEADER_REGEX,
        f"# FastAPI REST API ({routers} routers)",
        content,
    )

    # Page count: "**Pages (N):**"
    content = re.sub(
        PAGES_HEADER_REGEX,
        f"**Pages ({pages}):**",
        content,
    )

    if content == original:
        print("  CLAUDE.md: (no changes)")
        return True

    with open(CLAUDE_PATH, "w") as f:
        f.write(content)

    print("  CLAUDE.md: updated endpoint/router/page counts")
    return True


# ── Vocab parsing ───────────────────────────────────────────────────

def parse_vocab_canonical_list(vocab_content: str, kind: str) -> list[str]:
    """Extract canonical IDs for kind in {"session", "module"} from vocab §3.

    Locates the section header via VOCAB_CANONICAL_SECTION_REGEX, slices the
    body up to the next sibling-or-parent header (≤ same #-depth), then
    collects entries via VOCAB_CANONICAL_ENTRY_REGEX.
    """
    if kind not in ("session", "module"):
        raise ValueError(f"unknown kind: {kind}")

    header_re = re.compile(VOCAB_CANONICAL_SECTION_REGEX, re.MULTILINE)
    header_match = None
    for m in header_re.finditer(vocab_content):
        if m.group(1) == kind:
            header_match = m
            break
    if header_match is None:
        return []

    rest = vocab_content[header_match.end():]
    # Stop at any next header (sibling, parent, OR sub-section). Fields
    # described inside a "#### Session-level optional fields" subsection
    # would otherwise leak into the canonical id list (e.g. boulder_fallback
    # is a field descriptor, not a session_id).
    next_header_re = re.compile(r"^#+\s", re.MULTILINE)
    next_m = next_header_re.search(rest)
    section_body = rest[: next_m.start()] if next_m else rest

    entry_re = re.compile(VOCAB_CANONICAL_ENTRY_REGEX, re.MULTILINE)
    return entry_re.findall(section_body)


# ── Pre/post-update drift checks (F-38) ────────────────────────────

def parse_endpoint_header_total(claude_content: str) -> "int | None":
    m = re.search(ENDPOINT_TOTAL_PARSE_REGEX, claude_content)
    return int(m.group(1)) if m else None


def diagnostic_pre_update(real_count: int) -> None:
    """Pre-sync diagnostic: log drift between code and CLAUDE.md header.

    Not a warning — drift here is normal when sync is about to fix it.
    """
    if not os.path.exists(CLAUDE_PATH):
        return
    with open(CLAUDE_PATH) as f:
        pre = f.read()
    pre_header = parse_endpoint_header_total(pre)
    if pre_header is None:
        print(
            "  ℹ️  CLAUDE.md: cannot parse 'N endpoints total' header "
            "(regex broken? See ENDPOINT_TOTAL_PARSE_REGEX)."
        )
    elif pre_header != real_count:
        print(
            f"  ℹ️  CLAUDE.md endpoint drift detected: "
            f"header={pre_header}, code={real_count} (will sync)"
        )


def guardrail_post_update(real_count: int, warnings: list[str]) -> None:
    """Post-sync guardrail: if drift persists after update_claude(), emit warning.

    A POST-SYNC DRIFT means the auto-update did not apply — typically because
    a regex in update_claude() does not match the live doc text (RC-1 class).
    """
    if not os.path.exists(CLAUDE_PATH):
        return
    with open(CLAUDE_PATH) as f:
        post = f.read()
    post_header = parse_endpoint_header_total(post)
    if post_header is None:
        warnings.append(
            "CLAUDE.md: cannot parse endpoint header line. update_claude() "
            "regex may not match current text. See ENDPOINT_HEADER_REGEX."
        )
    elif post_header != real_count:
        warnings.append(
            f"POST-SYNC DRIFT: CLAUDE.md endpoint header is {post_header} "
            f"but code has {real_count} endpoints. update_claude() did not "
            f"apply the fix — likely a broken regex. "
            f"See ENDPOINT_HEADER_REGEX in scripts/sync_status.py."
        )


# ── Validation ─────────────────────────────────────────────────────

def validate(endpoints: int) -> list[str]:
    """Run validation checks and return warnings."""
    warnings: list[str] = []

    template_files = sorted([
        os.path.splitext(os.path.basename(f))[0]
        for f in glob.glob(os.path.join(REPO_ROOT, "backend/catalog/templates/v1/*.json"))
    ])
    session_files = sorted([
        os.path.splitext(os.path.basename(f))[0]
        for f in glob.glob(os.path.join(REPO_ROOT, "backend/catalog/sessions/v1/*.json"))
    ])

    vocab_content = None
    if os.path.exists(VOCAB_PATH):
        with open(VOCAB_PATH) as f:
            vocab_content = f.read()

    # Check disk → vocab (file exists but not listed)
    if vocab_content is not None:
        for t in template_files:
            if f"- `{t}`" not in vocab_content:
                warnings.append(
                    f"vocabulary_v1.md: module template '{t}' exists on disk but "
                    f"not in canonical list"
                )
        for s in session_files:
            if f"- `{s}`" not in vocab_content:
                warnings.append(
                    f"vocabulary_v1.md: session template '{s}' exists on disk but "
                    f"not in canonical list"
                )

    # Check vocab → disk (listed but no file) — F-37
    if vocab_content is not None:
        disk_templates = set(template_files)
        disk_sessions = set(session_files)
        for tid in parse_vocab_canonical_list(vocab_content, "module"):
            if tid not in disk_templates:
                warnings.append(
                    f"vocabulary_v1.md: module template '{tid}' listed in canonical "
                    f"list but no file at backend/catalog/templates/v1/{tid}.json"
                )
        for sid in parse_vocab_canonical_list(vocab_content, "session"):
            if sid not in disk_sessions:
                warnings.append(
                    f"vocabulary_v1.md: session template '{sid}' listed in canonical "
                    f"list but no file at backend/catalog/sessions/v1/{sid}.json"
                )

    # Check CLAUDE.md endpoint table row count matches declared total
    if os.path.exists(CLAUDE_PATH):
        with open(CLAUDE_PATH) as f:
            claude = f.read()
        table_rows = len(re.findall(
            ENDPOINT_TABLE_ROW_REGEX, claude, re.MULTILINE
        ))
        declared = re.search(ENDPOINT_TOTAL_PARSE_REGEX, claude)
        if declared and table_rows != int(declared.group(1)):
            warnings.append(
                f"CLAUDE.md: endpoint table has {table_rows} rows "
                f"but header declares {declared.group(1)}"
            )

    return warnings


# ── Safety net ─────────────────────────────────────────────────────

SYNC_FILES = {"PROJECT_BRIEF.md", "README.md"}


def check_uncommitted_work() -> None:
    """Abort if non-sync files are uncommitted (staged or unstaged)."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    dirty = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        # porcelain format: "XY filepath" — strip status prefix
        filepath = line[3:].strip().strip('"')
        basename = filepath.split("/")[-1] if "/" in filepath else filepath
        if basename not in SYNC_FILES:
            dirty.append(filepath)

    if dirty:
        print("\n⚠️  UNCOMMITTED WORK FILES DETECTED!")
        print("Commit your work before running sync_status.py:\n")
        for f in dirty:
            print(f"  - {f}")
        # D255: this used to print "Run: git add -A && git commit". When a second
        # Claude session is working in the same tree, some of the files above are
        # NOT yours, and `add -A` packages them into your commit under your brief
        # id — the exact failure of 2026-07-20 (B288 vs A245 Phase D). Never
        # advise a blanket stage from here.
        print("\n⚠️  CHECK EVERY FILE ABOVE IS YOURS before staging.")
        print("   Another Claude session may be working in this same tree")
        print("   (see 'Session isolation' in CLAUDE.md). Files you do not")
        print("   recognise belong to someone else's brief — do not commit them.")
        print("\nStage explicit paths, never -A:")
        print("   git commit -m '<brief-id>: <description>' -- <your-file> ...")
        sys.exit(1)


# ── Main ────────────────────────────────────────────────────────────

def main() -> int:
    check_uncommitted_work()
    print("Collecting counts...")
    counts = collect_counts()
    endpoints = dict(counts)["API endpoints"]
    routers = count_routers()

    for label, value in counts:
        print(f"  {label}: {value}")
    print(f"  Routers: {routers}")

    print()
    print("Pre-sync diagnostics...")
    diagnostic_pre_update(endpoints)

    print()
    print("Syncing files...")
    pages = dict(counts)["Frontend pages"]
    update_marker_file(BRIEF_PATH, counts, "PROJECT_BRIEF.md")
    update_marker_file(README_PATH, counts, "README.md")
    update_claude(endpoints, routers, pages)

    print()
    warnings = validate(endpoints)
    guardrail_post_update(endpoints, warnings)
    if warnings:
        for w in warnings:
            print(f"  ⚠️  {w}")
    else:
        print("  ✅ All validations passed.")

    print()
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

    # Optional: trim completed roadmap items
    # Uncomment to auto-trim on every sync:
    # import subprocess
    # subprocess.run([sys.executable, str(Path(__file__).parent / "trim_roadmap.py")], check=True)
