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
- Cleanup after merge: `python scripts/worktrees.py --clean` (see *Leftover worktrees* below).

**Untangling (only with the other session stopped):** back up both sessions' uncommitted files to disk **before** any git command → `git branch salvage/<sha> <sha>` on the mixed commit → `git cherry-pick -n` + surgical removal of the other brief's files → `git commit -C <sha>` to preserve message and author → verify file-by-file against the backups before deleting anything.

## Leftover worktrees and branches (D286, 2026-10-23)

Worktrees solved the shared-tree races but created a slower kind of mess: nothing removed a worktree once its
work reached main. Two failure modes: merged worktrees piling up on disk (over 1 GB each with `node_modules` and
`.next`), and — worse — **unmerged work forgotten in a worktree**: B350 sat outside main for three weeks while the
roadmap called it closed (lesson of 2026-09-28).

`scripts/worktrees.py` makes both visible and cleans only what is provably safe:

| Where | What runs |
|---|---|
| every Claude session start | `SessionStart` hook in `.claude/settings.json` (versioned since D286) → `worktrees.py --quiet` |
| every `git push` | end of `.githooks/pre-push`, after the counters check → `--quiet`, never blocks; a push to `main` passes its sha with `--pushing-main`, so the brief being pushed is not reported as "not on main" |
| `start_brief.py` | prints the same report before creating the new worktree |
| after a merge | `python scripts/worktrees.py --clean` (`--dry-run` to preview) |

States in the report: **IN CORSO** (uncommitted, hidden or mid-rebase files, or commits not on origin/main, touched
< 3 days ago — another session's work, or yours), **FERMO** (same, idle ≥ 3 days: tell Daniele and decide together),
**SU MAIN** (clean, everything on origin/main), **VUOTO** (never had a commit of its own), **SPARITO** (directory gone:
report only — `git worktree repair <new path>` if it was moved, `git worktree prune` once you have checked it). It also
lists local branches with no worktree, remote branches other than main (report only: `git push origin --delete …` is
left to a human), `climb-agent-*` directories that look like worktrees git no longer knows (a directory with its own
`.git` is another repo and is skipped), stashes, and a primary worktree that is dirty or off main. `--quiet` prints
nothing when there is only the primary, clean, on main.

**"On main" means nothing would be lost**: an ancestor of origin/main; or merging it would change nothing (`git
merge-tree --write-tree origin/main <sha>` returns exactly origin/main's tree — unlike `git cherry`, this does not wave
through content that lives only in a merge commit, a conflict resolution or an "evil merge", nor a whitespace-only fix:
patch-ids ignore whitespace, Python indentation does not); or origin/main holds its **exact copy** — a non-merge commit with
the same author, author date and message **and** the same change byte for byte (`git patch-id --verbatim` on a
`--binary` diff), as a conflict-free cherry-pick or rebase leaves; so a series cherry-picked onto main counts even if a
later commit of the same brief revised an earlier one. Identity alone is not enough: `commit --amend --no-edit` and
`--fixup` + autosquash keep author, date and message while adding work. **Every commit counts,
not just the tip**: the history of HEAD and every commit its reflogs remember (worktree `logs/HEAD`, branch reflog,
`ORIG_HEAD`, `refs/worktree/*`, `refs/bisect/*`). A commit followed by its revert, or dropped with `reset --hard`, has a
tip "equal to main" but the work exists only there — removing the worktree and `update-ref -d` on its branch delete those
reflogs, so the commit would become unreachable. What a **deliberate rewrite** replaced does not count: for a
`commit (amend)` reflog entry, `old ^new` (the commit before the amend); for a finished rebase (`rebase … (finish)`,
also `pull --rebase … (finish)`), only the commits of `old ^new` that have an heir among the commits the rebase
**wrote** — `new ^old ^onto`, with `onto` read from the reflog entry (same author, author date, message); a
same-identity commit already on main is not an heir, and without `onto` nothing is replaced. Never the result (after a
rebase and a `reset --hard` the rebased copy is the only one left), never ancestors the rewrite did not touch, never an
aborted rebase (it leaves only `rebase (start)`), and never a commit the rebase dropped (`--skip`, `drop`, a wrong
`--onto`, or one git skipped as "previously applied" because its whitespace-insensitive patch-id matched a copy on
main): it has no heir, so it stays and a human decides. A folded `fixup!` counts only if its content is on main. A commit a conflict resolution emptied (rebase drops it) is kept too:
from the reflog it cannot be told apart from a `--skip`. Intermediate commits of a squash merge that a later commit
revised are kept for a human to look at (squash is not used here). `origin/main` is always the full ref
`refs/remotes/origin/main`, so a local branch named `origin/main` cannot shadow it. A worktree whose history or reflogs
hold work not on main is **IN CORSO / FERMO**, not SU MAIN, so after 3 days it is escalated like any forgotten work.

**What `--clean` removes, and why it loses nothing.** A worktree goes only when all of these hold, re-checked right
before the removal:
- no modified or untracked file — status runs with `--untracked-files=normal` and `-c status.showUntrackedFiles=normal`,
  because with `no` in the user's config both the script and the internal check of `git worktree remove` would miss
  untracked files — and no file hidden by `--skip-worktree` / `--assume-unchanged` (`git ls-files -v`);
- no rebase, merge, cherry-pick, revert or bisect in progress (its branch also counts as checked out);
- history and reflogs entirely on main (above);
- no ignored file that does not regenerate: **`git worktree remove` without `--force` refuses modified and untracked
  files but deletes ignored ones silently** (`.env`, `reports/`, `out/`…); only `node_modules`, `.next`, `__pycache__`,
  test caches and the frontend build outputs are allowed;
- not on `main`, not locked (`git worktree lock`), no process with its cwd inside (`lsof`; without `lsof` nothing
  goes), and idle ≥ 2 h — ≥ 24 h if it never had a commit of its own (a fast-forward or `reset` to a newer main is not
  a commit, so a brief that was just started and updated is never swept).

Claude sessions here keep their cwd in the primary and reach worktrees by absolute path, so `lsof` does not see them:
a merged worktree idle for 2 h is removed even if its session is still open. Nothing is lost (it is all on main);
the session recreates it with `start_brief.py`, or keeps it with `git worktree lock`.

Local branches without a worktree go when their history and reflog are on main and the reflog is ≥ 2 h old (a fresh
`salvage/<sha>` stays); they are re-checked right before deletion. Branches are deleted with `git update-ref -d <ref>
<verified sha>`, so one that moved after the check stays; `main` is never deleted. `--clean` fetches first and aborts if
the fetch fails (never decide on a stale origin/main); the fetch **never prunes** (`-c fetch.prune=false`, whatever the
config says): a remote-tracking ref whose branch was deleted on origin is dropped only if its history is on main,
otherwise it is kept and reported as the last local copy. A missing worktree (SPARITO) is never pruned automatically:
the report reads its leftover `logs/HEAD` and says whether `git worktree prune` would lose commits. A worktree the
script cannot read shows as ERRORE without silencing the others. `--force` is never used. Every git call runs with
`GIT_OPTIONAL_LOCKS=0` (the report never rewrites another session's index) and without `GIT_DIR`, `GIT_INDEX_FILE` &
co. — inside the pre-push hook git exports them for the pushing worktree, and every other worktree would be read
against that index. Tests: `backend/tests/test_d286_worktrees_script.py` (real repos in `tmp_path`, ageing via mtime;
one regression test per defect found by the adversarial review rounds).
