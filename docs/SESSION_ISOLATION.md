# Session isolation — storia e dettagli

> Testo completo con gli incidenti che hanno motivato le regole (2026-07-19, 2026-07-20, 2026-07-29). Spostato da `CLAUDE.md` in D285 (2026-10-17). Le regole operative restano in `CLAUDE.md`.

## Session isolation (parallel Claude sessions)

More than one Claude session can be open on this repo at the same time. They share **one** working tree, **one** index and **one** HEAD — so without isolation they corrupt each other's work.

**Preflight — run before creating a branch or touching a file, every brief, no exceptions:**

```bash
git status --short          # must be empty
git branch --show-current   # must be main
```

"I'm on main with a clean tree" is an **assumption until these two commands prove it**. This has already gone wrong twice (2026-07-19 D252/B279, 2026-07-20 B288/A245-D): the second time, `git checkout -b` ran while the tree sat on another session's dirty branch, so the new branch was born on top of foreign work and that session's `git add -A` packaged two files of the other brief into a commit with the wrong message, on the wrong branch.

**Any brief that will produce a commit → work in a dedicated worktree. Always, not only when the preflight fails.**

The rule used to be conditional ("worktree *if* the tree is dirty"). That is not enough, and it failed a third time on 2026-07-29 (B308 vs B309): **the preflight is a point-in-time check**. Both sessions found a clean tree on `main`, both stayed in the shared tree, and forty minutes later one of them ran `git checkout -b` — moving HEAD for the other, whose commit then landed on the wrong branch. Nothing in a conditional rule protects you *during* the work.

A `pre-commit` hook now enforces it: committing on a non-`main` branch **in the primary worktree** is blocked (override with `ALLOW_PRIMARY_BRANCH_COMMIT=1` when you really mean it).

```bash
python scripts/start_brief.py <BRIEF-ID> <slug>      # preflight + worktree + branch from origin/main
```

Or by hand: `git worktree add ../climb-agent-<brief> -b brief/<ID>-<slug> origin/main`

Rules that hold in any shared tree:

- **Never `git add -A` when the tree was not clean at brief start.** Stage explicit paths. `git add -A` is only safe when every dirty file is provably yours.
- **Never `git checkout` / `git switch` in a shared tree**: it moves HEAD for the other session too.
- A worktree needs a real `npm ci` in `frontend/` — symlinking `node_modules` fails the build (`Symlink node_modules is invalid, it points out of the filesystem root`).
- `backend/data/user_state.json` is a tracked fixture that the pytest suite rewrites: check it did not sneak into the commit.
- Cleanup after merge: `git worktree remove ../climb-agent-<brief>` then delete the branch.

**Untangling (only with the other session stopped):** back up both sessions' uncommitted files to disk **before** any git command → `git branch salvage/<sha> <sha>` on the mixed commit → `git cherry-pick -n` + surgical removal of the other brief's files → `git commit -C <sha>` to preserve message and author → verify file-by-file against the backups before deleting anything.
