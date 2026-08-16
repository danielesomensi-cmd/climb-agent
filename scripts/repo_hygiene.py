#!/usr/bin/env python3
"""climb-agent repo hygiene check — read-only diagnostic."""

import os
import subprocess
from pathlib import Path

# D269 (2026-08-02) — docs + roadmap audit: `docs/audit/D269_roadmap_docs_audit.md`.
# Covered: roadmap pruning against the code, doc alignment (CLAUDE.md / PROJECT_BRIEF /
# user guide), archival of closed audit reports. NOT covered: a full code review —
# for that the last one is still D254 (2026-07-20).
# Previous hygiene audit: D237, now at `_archive/docs/audit/D237_repo_hygiene_2026-05-11.md`.
LAST_AUDIT_DATE = "2026-08-02"

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
ROADMAP = DOCS_DIR / "ROADMAP_CURRENT.md"

ROOT_WHITELIST = {
    "README.md", "CLAUDE.md", "PROJECT_BRIEF.md", "Procfile",
    "pyproject.toml", "railway.json", "requirements.txt", ".gitignore",
    # AUTH_AUDIT.md: deliberately kept at root (auth reference for the external
    # Kilter-Up project); referenced by D236/D237 audit docs — do not relocate.
    "AUTH_AUDIT.md",
    # AGENTS.md: instructions for non-Claude agents. Untracked on purpose
    # (listed in .git/info/exclude), so it is never a repo-hygiene problem —
    # but it does sit on disk, and flagging it every run trained us to ignore
    # the warning (D269).
    "AGENTS.md",
}

COMPLETED_MARKERS = {"CLOSED", "FINAL", "COMPLETED", "Done", "✅ Done"}

warnings = 0
oks = 0
infos = 0


def warn(msg: str):
    global warnings
    warnings += 1
    print(f"[WARN] {msg}")


def ok(msg: str):
    global oks
    oks += 1
    print(f"[OK] {msg}")


def info(msg: str):
    global infos
    infos += 1
    print(f"[INFO] {msg}")


def check_completed_briefs():
    """Scan docs/ for files with completion markers near the top."""
    if not DOCS_DIR.is_dir():
        return
    found = False
    for f in sorted(DOCS_DIR.glob("*.md")):
        try:
            lines = f.read_text(encoding="utf-8").splitlines()[:10]
        except Exception:
            continue
        for line in lines:
            for marker in COMPLETED_MARKERS:
                if marker in line:
                    warn(f"{f.relative_to(REPO_ROOT)} — contains \"{marker}\", candidate for archive")
                    found = True
                    break
            else:
                continue
            break
    if not found:
        ok("No completed brief docs found in docs/")


def check_roadmap_bloat():
    """Warn if ROADMAP_CURRENT.md exceeds 350 lines."""
    if not ROADMAP.is_file():
        ok("ROADMAP_CURRENT.md not found (nothing to check)")
        return
    line_count = len(ROADMAP.read_text(encoding="utf-8").splitlines())
    if line_count > 350:
        warn(f"ROADMAP_CURRENT.md — {line_count} lines (target ≤350)")
    else:
        ok(f"ROADMAP_CURRENT.md — {line_count} lines (≤350)")


def check_stale_root_files():
    """List unexpected files at repo root."""
    found = False
    for f in sorted(REPO_ROOT.iterdir()):
        if f.name.startswith(".") and f.name != ".gitignore":
            continue
        if f.is_dir():
            continue
        if f.suffix in (".md", ".json", ".py") and f.name not in ROOT_WHITELIST:
            warn(f"Unexpected file at root: {f.name}")
            found = True
    if not found:
        ok("No unexpected files at repo root")


def check_tracked_ds_store():
    """Check for tracked .DS_Store files."""
    result = subprocess.run(
        ["git", "ls-files", "*.DS_Store"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    files = result.stdout.strip()
    if files:
        for f in files.splitlines():
            warn(f"Tracked .DS_Store: {f}")
    else:
        ok("No tracked .DS_Store")


def check_large_untracked():
    """Find files >500K at root or in docs/ not in .gitignore."""
    SIZE_LIMIT = 500 * 1024
    # D276: the roadmap archive is *meant* to grow — every trim_roadmap.py run
    # appends to it, so it crossed 500K the first time the roadmap was pruned
    # hard. Warning about it would fire on every run from now on and teach the
    # reader to skim past hygiene output, which is the opposite of the point.
    # This check exists to catch a binary committed by accident, not the file
    # the workflow is designed to fill.
    EXEMPT = {"ROADMAP_v2.md"}
    found = False
    # Check repo root (non-recursive) and docs/
    search_dirs = [REPO_ROOT]
    if DOCS_DIR.is_dir():
        search_dirs.append(DOCS_DIR)

    for d in search_dirs:
        for f in d.iterdir():
            if f.is_dir():
                continue
            if f.name.startswith("."):
                continue
            if f.name in EXEMPT:
                continue
            try:
                if f.stat().st_size > SIZE_LIMIT:
                    # Check if git-ignored
                    r = subprocess.run(
                        ["git", "check-ignore", "-q", str(f)],
                        capture_output=True, cwd=REPO_ROOT,
                    )
                    if r.returncode != 0:  # not ignored
                        warn(f"Large file ({f.stat().st_size // 1024}K): {f.relative_to(REPO_ROOT)}")
                        found = True
            except Exception:
                continue
    if not found:
        ok("No large untracked files")


def check_brief_count():
    """Count A/B/C/D briefs since last audit."""
    result = subprocess.run(
        ["git", "log", "--oneline", f"--since={LAST_AUDIT_DATE}"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    lines = [l for l in result.stdout.strip().splitlines() if l]
    brief_count = 0
    for line in lines:
        # Format: "hash message" — check if message starts with A/B/C/D prefix pattern
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        msg = parts[1]
        if any(msg.startswith(f"{p}") for p in ("A", "B", "C", "D")) and any(c.isdigit() for c in msg[:5]):
            brief_count += 1
    if brief_count >= 10:
        warn(f"{brief_count} briefs since last audit ({LAST_AUDIT_DATE}) — consider running a full audit")
    else:
        info(f"{brief_count} briefs since last audit ({LAST_AUDIT_DATE}) — next audit around brief #10")


def main():
    print(f"\n=== climb-agent repo hygiene check ===\n")

    check_completed_briefs()
    check_roadmap_bloat()
    check_stale_root_files()
    check_tracked_ds_store()
    check_large_untracked()
    check_brief_count()

    print(f"\n=== Done. {warnings} warnings, {oks} OK, {infos} info ===")
    if warnings == 0:
        print("✅ Repo is clean. No action needed.")
    print()


if __name__ == "__main__":
    main()
