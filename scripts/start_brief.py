#!/usr/bin/env python3
"""Start a brief in an isolated git worktree.

Why this exists: more than one Claude session can be open on this repo, and they
share one working tree, one index and one HEAD. Twice (2026-07-19 D252/B279,
2026-07-20 B288/A245-D) a session branched off another session's dirty tree and
their `git add -A` swept foreign files into the wrong commit on the wrong branch.
A worktree makes that impossible; this script makes the worktree the path of
least resistance.

Usage:
    python scripts/start_brief.py B289 used-grade
    python scripts/start_brief.py B289 used-grade --check   # preflight only

The new worktree is always branched from **origin/main**, never from whatever
HEAD happens to be — that is precisely the mistake being prevented.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIEF_RE = re.compile(r"^[ABCD]\d+$|^[ABCD]-[A-Z0-9-]+$")


def main_worktree_root() -> Path:
    """Path of the PRIMARY worktree.

    `REPO_ROOT` is the tree this script runs from, which may itself be a
    worktree — deriving the new worktree name from it produced nonsense like
    `climb-agent-d255-d999`. The first entry of `git worktree list` is always
    the main worktree.
    """
    listing = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    ).stdout
    for line in listing.splitlines():
        if line.startswith("worktree "):
            return Path(line.split(" ", 1)[1].strip())
    return REPO_ROOT


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=REPO_ROOT
    )
    if check and result.returncode != 0:
        print(f"✗ git {' '.join(args)}\n{result.stderr.strip()}")
        sys.exit(1)
    return result.stdout.strip()


def preflight() -> bool:
    """Report the two facts a brief must never assume. True when the shared tree is usable."""
    branch = git("branch", "--show-current")
    dirty = [ln for ln in git("status", "--porcelain").splitlines() if ln.strip()]

    print("Preflight:")
    print(f"  branch corrente : {branch or '(detached HEAD)'}")
    print(f"  file sporchi    : {len(dirty)}")
    for line in dirty[:10]:
        print(f"      {line}")
    if len(dirty) > 10:
        print(f"      … e altri {len(dirty) - 10}")

    clean_and_on_main = (branch == "main") and not dirty
    if clean_and_on_main:
        print("  → tree condiviso pulito su main.")
    else:
        reasons = []
        if branch != "main":
            reasons.append(f"non sei su main (sei su {branch or 'detached HEAD'})")
        if dirty:
            reasons.append(f"{len(dirty)} file non committati — potrebbero essere di un'altra sessione")
        print(f"  → worktree OBBLIGATORIO: {'; '.join(reasons)}")
    return clean_and_on_main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief_id", nargs="?", help="es. B289, A246, D255")
    parser.add_argument("slug", nargs="?", help="es. used-grade")
    parser.add_argument("--check", action="store_true", help="solo preflight, non crea nulla")
    args = parser.parse_args()

    on_clean_main = preflight()

    if args.check or not args.brief_id:
        if not args.brief_id:
            print("\n(nessun brief id: solo preflight. Uso: start_brief.py B289 used-grade)")
        return 0

    brief_id = args.brief_id.upper()
    if not BRIEF_RE.match(brief_id):
        print(f"\n✗ brief id '{brief_id}' non valido: atteso B289 / A246 / D255 / B-QUICKADD-ADJUSTMENTS")
        return 1
    if not args.slug:
        print("\n✗ manca lo slug. Uso: start_brief.py B289 used-grade")
        return 1

    slug = args.slug.strip().lower().replace(" ", "-").replace("_", "-")
    branch = f"brief/{brief_id}-{slug}"
    base = main_worktree_root()
    worktree = base.parent / f"{base.name}-{brief_id.lower()}"

    existing_branches = git("branch", "--list", branch)
    if existing_branches:
        print(f"\n✗ il branch {branch} esiste già. Scegli un altro id/slug o riprendi quel branch.")
        return 1
    if worktree.exists():
        print(f"\n✗ {worktree} esiste già. Rimuovilo con: git worktree remove {worktree}")
        return 1

    print(f"\nFetch di origin…")
    git("fetch", "origin")

    print(f"Creo il worktree da origin/main (NON da HEAD):")
    print(f"  branch   : {branch}")
    print(f"  worktree : {worktree}")
    git("worktree", "add", str(worktree), "-b", branch, "origin/main")

    print("\n✅ Pronto. Prossimi passi:\n")
    print(f"  cd {worktree}")
    print("  # se il brief tocca frontend/:")
    print("  cd frontend && npm ci      # symlink a node_modules NON funziona (Turbopack)")
    print("\nA fine brief:")
    print(f"  git worktree remove {worktree} && git branch -d {branch}")
    if on_clean_main:
        print("\nNota: il tree condiviso era pulito su main, quindi il worktree non era")
        print("obbligatorio — ma resta la scelta giusta se un'altra sessione può aprirsi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
