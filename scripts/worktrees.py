#!/usr/bin/env python3
"""Worktree e branch residui: report in sola lettura e pulizia sicura (D286).

Perché esiste: ogni brief vive in un worktree suo (`start_brief.py`, C261), ma
niente lo toglie quando il lavoro arriva su main. Si sporca in due modi:
  1. worktree e branch già su main lasciati sul disco (con `node_modules` e
     `.next` sono più di 1 GB l'uno);
  2. lavoro MAI mergiato dimenticato in un worktree: B350 è rimasto tre
     settimane fuori da main con la roadmap che lo dava chiuso.
Questo script li fa vedere all'avvio di ogni sessione Claude (hook SessionStart
in `.claude/settings.json`) e a ogni push (`.githooks/pre-push`), e toglie solo
ciò che è dimostrabilmente già su origin/main.

Uso:
    python scripts/worktrees.py                    # report completo, sola lettura
    python scripts/worktrees.py --quiet            # zitto se non c'è niente da dire (hook)
    python scripts/worktrees.py --clean --dry-run  # cosa toglierebbe
    python scripts/worktrees.py --clean            # fetch, poi toglie

Un commit è «su main» se è antenato di origin/main, se unirlo non cambierebbe
niente (`git merge-tree` dà esattamente l'albero di origin/main: un merge commit
con contenuto suo o una correzione di soli spazi no), o se main ne ha la copia
(stesso autore, data d'autore e messaggio: cherry-pick e rebase la lasciano anche
con i conflitti risolti). Conta OGNI commit della storia e dei reflog, non solo
la punta: un lavoro seguito dal suo revert, o buttato con un `reset --hard`,
esiste solo lì. Non conta ciò che una riscrittura voluta ha sostituito (vecchio
^nuovo di un `commit --amend` o di un rebase finito, anche da `pull --rebase`).

`--clean` toglie un worktree solo se: non è il primario né su main; non ha file
modificati, non tracciati o nascosti (skip-worktree / assume-unchanged); non ha
un rebase/merge/cherry-pick/bisect in corso; storia e reflog tutti su main; non
ha file ignorati che non si rigenerano (`git worktree remove` cancella in
silenzio `.env`, `reports/`…); non è bloccato (`git worktree lock`); nessun
processo ha la cwd dentro; è fermo da almeno 2 ore (24 se non ha mai avuto un
commit suo). Ricontrolla tutto subito prima di toglierlo, non usa mai `--force`
e cancella il branch solo se punta ancora al commit verificato. Toglie anche i
branch locali senza worktree con storia e reflog su main, fermi da 2 ore. I
worktree spariti dal disco e i branch remoti si segnalano soltanto; il fetch non
pota mai, nemmeno se la config lo chiede. Le sessioni Claude lavorano nei worktree con path assoluti, quindi
`lsof` non le vede: un worktree già su main e fermo da 2 ore si toglie anche se
la sessione è ancora aperta — senza perdere niente, si ricrea con start_brief.

Tutti i comandi git girano con GIT_OPTIONAL_LOCKS=0 (il report non riscrive
l'index di un'altra sessione) e senza le variabili GIT_DIR & co. che git passa
agli hook (dentro il pre-push puntano al worktree che sta pushando).
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE = "refs/remotes/origin/main"   # nome completo: un branch locale «origin/main» non lo scavalca
BASE_LABEL = "origin/main"
MERGED_IDLE_S = 2 * 3600
EMPTY_IDLE_S = 24 * 3600
STALE_IDLE_S = 3 * 24 * 3600
BRANCH_IDLE_S = 2 * 3600

# `git rev-parse --local-env-vars`: dentro un hook puntano al repo di chi l'ha lanciato.
REPO_ENV_VARS = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT",
    "GIT_OBJECT_DIRECTORY", "GIT_DIR", "GIT_WORK_TREE", "GIT_IMPLICIT_WORK_TREE", "GIT_GRAFT_FILE",
    "GIT_INDEX_FILE", "GIT_NO_REPLACE_OBJECTS", "GIT_REPLACE_REF_BASE", "GIT_PREFIX",
    "GIT_SHALLOW_FILE", "GIT_COMMON_DIR",
)
# La config dell'utente non deve poter nascondere file allo status (né a quello
# interno di `git worktree remove`, che legge la stessa config).
GIT_CONFIG_PINS = ("-c", "status.showUntrackedFiles=normal", "-c", "core.quotePath=false")

# File ignorati che si ricreano da soli (npm ci, build, pytest). Tutto il resto
# — `.env`, `reports/`, `tmp/`, `_backups/`… — blocca la rimozione.
REGENERABLE_DIRS = {  # a qualunque profondità
    "node_modules", ".next", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".turbo",
}
REGENERABLE_PATHS = {  # dalla radice del worktree (`out/` alla radice NO: lì finiscono output di script)
    ".vercel", "frontend/.vercel", "frontend/out", "frontend/coverage",
    "frontend/next-env.d.ts", "frontend/tsconfig.tsbuildinfo", "frontend/public/sw.js",
}
REGENERABLE_SUFFIXES = (".pyc", ".DS_Store")

# Stato di un'operazione git a metà, nel gitdir del worktree.
IN_PROGRESS_MARKERS = (
    "rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "sequencer", "BISECT_LOG",
)
# Voci di reflog che vogliono dire «qui è nato un commit»; fast-forward, reset e
# checkout no (un worktree vuoto aggiornato a un main più nuovo resta vuoto).
# Voci di reflog che riscrivono di proposito il commit precedente: un amend, un
# rebase FINITO (anche da `pull --rebase`; uno interrotto con --abort lascia solo
# «rebase (start)»). Conta solo ciò che la voce ha sostituito: vecchio ^nuovo.
REWRITE_RE = re.compile(r"^(commit \(amend\)|(rebase|pull)\b[^:]*\(finish\):)")
OWN_COMMIT_RE = re.compile(
    r"^(commit|cherry-pick|revert|rebase( -i)? \((pick|squash|fixup|reword|edit)\))"
    r"|^(merge|pull)\b.*: Merge made by"
)


def git(*args: str, cwd: Path | None = None, check: bool = False, stdin: str | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in REPO_ENV_VARS}
    env["GIT_OPTIONAL_LOCKS"] = "0"
    result = subprocess.run(
        ["git", *GIT_CONFIG_PINS, *args], capture_output=True, text=True,
        cwd=cwd or REPO_ROOT, env=env, timeout=120, input=stdin,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result


def out(*args: str, cwd: Path | None = None) -> str:
    return git(*args, cwd=cwd, check=True).stdout.strip()


def common_dir() -> Path:
    return Path(out("rev-parse", "--path-format=absolute", "--git-common-dir"))


# ── «è già su main?» ─────────────────────────────────────────────────────────

_contained: dict[str, bool] = {}
_main_identities: set[str] | None = None
# Commit che il pre-push sta per mettere su main: nel report contano già come su main.
ASSUMED_ON_MAIN: list[str] = []


def reset_caches() -> None:
    global _main_identities
    _contained.clear()
    _main_identities = None


def contained(sha: str) -> bool:
    """`sha` è già su main: antenato, unirlo non cambierebbe niente, o main ne ha la copia."""
    if sha not in _contained:
        bases = [BASE, *ASSUMED_ON_MAIN]
        if any(git("merge-base", "--is-ancestor", sha, b).returncode == 0 for b in bases):
            _contained[sha] = True
        else:
            merged = git("merge-tree", "--write-tree", "--no-messages", BASE, sha)
            base_tree = out("rev-parse", f"{BASE}^{{tree}}")
            _contained[sha] = (merged.returncode == 0 and merged.stdout.split()[:1] == [base_tree]) or copied_on_main(sha)
    return _contained[sha]


IDENTITY_FORMAT = "%an%x1f%ae%x1f%at%x1f%B"


def copied_on_main(sha: str) -> bool:
    """Main ha un commit con lo stesso autore, la stessa data d'autore e lo stesso messaggio:
    la copia che fanno un cherry-pick o un rebase (anche con conflitti risolti), quindi il
    lavoro è arrivato su main anche se un commit successivo dello stesso brief lo ha rivisto."""
    global _main_identities
    row = git("log", "-1", f"--format=%P%x1e{IDENTITY_FORMAT}", sha).stdout
    parents, _, identity = row.partition("\x1e")
    if len(parents.split()) != 1:
        return False   # i merge commit si giudicano solo sul contenuto
    if _main_identities is None:
        raw = git("log", "--no-merges", f"--format={IDENTITY_FORMAT}%x1e", BASE).stdout
        _main_identities = {chunk.strip("\n") for chunk in raw.split("\x1e") if chunk.strip()}
    return identity.strip("\n") in _main_identities


def unmerged_count(sha: str) -> int:
    """Quanti commit di `sha` non sono su main (solo per il testo; decide `contained`)."""
    if contained(sha):
        return 0
    pending = out("rev-list", sha, f"^{BASE}").splitlines()
    plus = sum(1 for ln in out("cherry", BASE, sha).splitlines() if ln.startswith("+"))
    merges = int(out("rev-list", "--count", "--merges", sha, f"^{BASE}") or 0)
    return (plus + merges) or len(pending) or 1


def existing_commits(shas: set[str]) -> list[str]:
    if not shas:
        return []
    batch = git("cat-file", "--batch-check", stdin="\n".join(sorted(shas)) + "\n").stdout
    rows = (ln.split() for ln in batch.splitlines())
    return [row[0] for row in rows if len(row) >= 2 and row[1] == "commit"]


def reflog_entries(log: Path) -> list[tuple[str, str, str]]:
    """(vecchio, nuovo, messaggio) per ogni voce di un file di reflog."""
    entries = []
    try:
        lines = log.read_text(errors="replace").splitlines()
    except OSError:
        return entries
    for line in lines:
        head, _, message = line.partition("\t")
        parts = head.split(" ", 2)
        if len(parts) >= 2:
            entries.append((parts[0], parts[1], message))
    return entries


def off_main(live: set[str], logs: list[Path] = (), extra: set[str] = frozenset()) -> list[str]:
    """Commit che toglierli perderebbe: raggiungibili da `live`, dai reflog `logs` o da `extra`,
    e che unire in main cambierebbe.

    Ogni commit della storia conta, non solo la punta: un lavoro seguito dal suo
    revert ha una punta «uguale a main», ma il lavoro esiste solo lì. I commit
    riscritti apposta (valore vecchio di un `commit --amend` o di un rebase) non
    contano: l'utente li ha sostituiti.
    """
    tips, rewrites = set(live) | set(extra), []
    for log in logs:
        for old, new, message in reflog_entries(log):
            if new.strip("0"):
                tips.add(new)
            if old.strip("0") and new.strip("0") and old != new and REWRITE_RE.match(message):
                rewrites.append((old, new))
    # Riscritto è solo ciò che la voce ha sostituito (vecchio ^nuovo: la serie di
    # prima di un rebase, il commit prima di un amend), mai ciò che la storia viva usa ancora.
    rewritten: set[str] = set()
    for old, new in rewrites:
        if len(existing_commits({old, new})) == 2:
            rewritten |= set(rev_list([old], exclude=[new]))
    rewritten -= set(rev_list(existing_commits({t for t in live if t})))
    tips = existing_commits({t for t in tips if t and t not in rewritten})
    return [sha for sha in rev_list(tips) if sha not in rewritten and not contained(sha)]


def rev_list(tips: list[str], exclude: list[str] = ()) -> list[str]:
    """Commit raggiungibili da `tips` che non sono antenati di origin/main (né di `exclude`)."""
    if not tips:
        return []
    negated = [f"^{rev}" for rev in (BASE, *ASSUMED_ON_MAIN, *exclude)]
    return git("rev-list", "--stdin", stdin="\n".join(list(tips) + negated) + "\n").stdout.split()


# ── worktree ─────────────────────────────────────────────────────────────────


@dataclass
class Worktree:
    path: Path
    head: str = ""
    branch: str | None = None          # None = detached HEAD
    locked: bool = False
    prunable: bool = False
    dirty: list[str] = field(default_factory=list)
    hidden: list[str] = field(default_factory=list)       # skip-worktree / assume-unchanged
    operation: str = ""                # rebase/merge/… in corso
    operation_branch: str | None = None
    unmerged: int = 0
    progressed: bool = False           # un commit nato qui (o sul suo branch)?
    blocking_ignored: list[str] = field(default_factory=list)
    lost: list[str] = field(default_factory=list)          # commit (storia o reflog) non su main
    last_activity: float = 0.0
    state: str = ""                    # missing | error | active | stale | merged | empty
    removable: bool = False
    why_kept: str = ""

    @property
    def label(self) -> str:
        if self.branch:
            return self.branch
        if self.operation_branch:
            return f"{self.operation} di {self.operation_branch}"
        return f"detached {self.head[:7]}"


def list_worktrees() -> list[Worktree]:
    listing = out("worktree", "list", "--porcelain")
    trees: list[Worktree] = []
    for block in listing.split("\n\n"):
        wt: Worktree | None = None
        for line in block.splitlines():
            key, _, value = line.partition(" ")
            if key == "worktree":
                wt = Worktree(path=Path(value))
            elif wt is None:
                continue
            elif key == "HEAD":
                wt.head = value if value.strip("0") else ""   # tutti zeri: worktree --orphan senza commit
            elif key == "branch":
                wt.branch = value.removeprefix("refs/heads/")
            elif key == "locked":
                wt.locked = True
            elif key == "prunable":
                wt.prunable = True
        if wt is not None:
            trees.append(wt)
    return trees


def is_regenerable(rel: str) -> bool:
    rel = rel.rstrip("/")
    if rel.endswith(REGENERABLE_SUFFIXES):
        return True
    if any(rel == p or rel.startswith(p + "/") for p in REGENERABLE_PATHS):
        return True
    return any(part in REGENERABLE_DIRS for part in rel.split("/"))


def mtime(path: Path) -> float:
    try:
        return path.lstat().st_mtime
    except OSError:
        return 0.0


def newest_inside(path: Path, limit: int = 5000) -> float:
    """mtime più recente dentro una cartella non tracciata (quella della cartella cambia solo se cambiano le voci)."""
    newest, seen = mtime(path), 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in REGENERABLE_DIRS]
        for name in files:
            newest = max(newest, mtime(Path(root) / name))
            seen += 1
            if seen >= limit:
                return newest
    return newest


def parse_status(raw: str) -> tuple[list[str], list[str]]:
    """`status --porcelain -z`: (voci modificate/non tracciate, voci ignorate)."""
    dirty, ignored = [], []
    entries = raw.split("\0")
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if len(entry) < 4:
            continue
        code, rel = entry[:2], entry[3:]
        if code == "!!":
            ignored.append(rel)
        else:
            dirty.append(rel)
            if "R" in code or "C" in code:   # rinomina/copia: il path d'origine è la voce dopo
                i += 1
    return dirty, ignored


def reflog_has_own_commit(log: Path) -> bool:
    try:
        lines = log.read_text(errors="replace").splitlines()
    except OSError:
        return False
    return any(OWN_COMMIT_RE.search(line.partition("\t")[2]) for line in lines)


def admin_dir(wt: Worktree, common: Path) -> Path | None:
    """`.git/worktrees/<id>` di un worktree, anche se la sua cartella non c'è più."""
    target = os.path.realpath(wt.path / ".git")
    for candidate in (common / "worktrees").glob("*"):
        try:
            if os.path.realpath((candidate / "gitdir").read_text().strip()) == target:
                return candidate
        except OSError:
            continue
    return None


def inspect(wt: Worktree, now: float, common: Path) -> None:
    if wt.prunable or not wt.path.is_dir():
        wt.state = "missing"
        admin = admin_dir(wt, common)
        logs = [admin / "logs" / "HEAD"] if admin else []
        wt.lost = off_main({wt.head} if wt.head else set(), logs)
        return
    status = git("status", "--porcelain=v1", "-z", "--ignored", "--untracked-files=normal",
                 "--ignore-submodules=none", cwd=wt.path)
    gdir_res = git("rev-parse", "--absolute-git-dir", cwd=wt.path)
    if status.returncode != 0 or gdir_res.returncode != 0:
        wt.state, wt.why_kept = "missing", (status.stderr or gdir_res.stderr).strip() or "git status fallito"
        return
    gdir = Path(gdir_res.stdout.strip())
    wt.dirty, ignored = parse_status(status.stdout)
    wt.blocking_ignored = [rel for rel in ignored if not is_regenerable(rel)]
    for entry in git("ls-files", "-v", "-z", cwd=wt.path).stdout.split("\0"):
        tag, _, rel = entry.partition(" ")
        if rel and (tag == "S" or tag.islower()) and os.path.lexists(wt.path / rel):
            wt.hidden.append(rel)

    for marker in IN_PROGRESS_MARKERS:
        if (gdir / marker).exists():
            wt.operation = {"rebase-merge": "rebase", "rebase-apply": "rebase", "MERGE_HEAD": "merge",
                            "CHERRY_PICK_HEAD": "cherry-pick", "REVERT_HEAD": "revert",
                            "sequencer": "cherry-pick", "BISECT_LOG": "bisect"}[marker]
            break
    for name_file in ("rebase-merge/head-name", "rebase-apply/head-name", "BISECT_START"):
        try:
            name = (gdir / name_file).read_text().strip().removeprefix("refs/heads/")
        except OSError:
            continue
        if name and name != "detached HEAD":
            wt.operation_branch = name
            break

    wt.unmerged = unmerged_count(wt.head) if wt.head else 0
    branch_log = common / "logs" / "refs" / "heads" / wt.branch if wt.branch else None
    wt.progressed = reflog_has_own_commit(gdir / "logs" / "HEAD") or bool(
        branch_log and reflog_has_own_commit(branch_log))

    stamps = [mtime(wt.path)] + [mtime(gdir / name) for name in ("HEAD", "index", "logs/HEAD")]
    if branch_log:
        stamps.append(mtime(branch_log))
    for rel in wt.dirty:
        target = wt.path / rel
        stamps.append(newest_inside(target) if rel.endswith("/") else mtime(target))
    wt.last_activity = max(stamps)
    idle = now - wt.last_activity

    if not (wt.dirty or wt.hidden or wt.unmerged or wt.operation):
        # HEAD è su main: resta da guardare la sua storia e i commit che solo i
        # reflog ricordano (un reset, un checkout via da un detached), che
        # `git worktree remove` e `update-ref -d` cancellerebbero.
        logs = [gdir / "logs" / "HEAD"] + ([branch_log] if branch_log else [])
        extra = set(out("for-each-ref", "--format=%(objectname)", "refs/worktree", "refs/bisect",
                        cwd=wt.path).split())
        try:
            extra.add((gdir / "ORIG_HEAD").read_text().strip())
        except OSError:
            pass
        wt.lost = off_main({wt.head}, logs, extra)
    if wt.dirty or wt.hidden or wt.unmerged or wt.operation or wt.lost:
        wt.state = "stale" if idle >= STALE_IDLE_S else "active"
        wt.why_kept = "lavoro non su main"
        return
    wt.state = "merged" if wt.progressed else "empty"
    threshold = MERGED_IDLE_S if wt.state == "merged" else EMPTY_IDLE_S
    if wt.branch == "main":
        wt.why_kept = "è main"
    elif wt.locked:
        wt.why_kept = "bloccato (git worktree lock)"
    elif wt.blocking_ignored:
        wt.why_kept = "file ignorati da guardare: " + ", ".join(wt.blocking_ignored[:5])
    elif idle < threshold:
        wt.why_kept = f"toccato {ago(idle)} fa (soglia {ago(threshold)})"
    else:
        wt.removable = True


@dataclass
class Branch:
    name: str
    sha: str
    committed: float
    unmerged: int
    last_activity: float = 0.0


def branch_unmerged(sha: str, *logs: Path) -> int:
    """Commit non su main di un branch: dalla punta, o dalla sua storia e dai suoi reflog."""
    return unmerged_count(sha) or len(off_main({sha}, list(logs)))


def busy_branches(trees: list[Worktree]) -> set[str]:
    return {name for wt in trees for name in (wt.branch, wt.operation_branch) if name}


def stray_branches(trees: list[Worktree], common: Path) -> list[Branch]:
    """Branch locali (non main) che nessun worktree ha in checkout, nemmeno a metà di un rebase."""
    busy = busy_branches(trees)
    rows = out("for-each-ref", "refs/heads", "--format=%(refname) %(objectname) %(committerdate:unix)")
    branches = []
    for row in rows.splitlines():
        ref, sha, ts = row.split(" ")
        name = ref.removeprefix("refs/heads/")
        if name == "main" or name in busy:
            continue
        # Attività del branch = il suo reflog (la data del commit dice quando è nato il commit, non il branch).
        activity = mtime(common / "logs" / ref) or float(ts or 0)
        branches.append(Branch(name, sha, float(ts or 0), branch_unmerged(sha, common / "logs" / ref), activity))
    return branches


def remote_branches(common: Path) -> list[Branch]:
    rows = out("for-each-ref", "refs/remotes/origin", "--format=%(refname) %(objectname) %(committerdate:unix) %(symref)")
    branches = []
    for row in rows.splitlines():
        ref, sha, ts, *symref = row.split(" ")
        if ref in ("refs/remotes/origin/HEAD", BASE) or any(symref):
            continue
        local_log = common / "logs" / "refs" / "heads" / ref.removeprefix("refs/remotes/origin/")
        branches.append(Branch(ref.removeprefix("refs/remotes/"), sha, float(ts or 0),
                               branch_unmerged(sha, common / "logs" / ref, local_log)))
    return branches


def orphan_dirs(trees: list[Worktree], common: Path) -> list[Path]:
    """Cartelle `climb-agent-*` accanto al primario che sembrano worktree ma git non li conosce.

    Una cartella con una `.git` sua è un altro repo, non un residuo: non si segnala.
    """
    primary = trees[0].path
    known = {os.path.realpath(wt.path) for wt in trees}
    orphans = []
    for p in sorted(primary.parent.glob(f"{primary.name}-*")):
        if not p.is_dir() or os.path.realpath(p) in known or (p / ".git").is_dir():
            continue
        dotgit = p / ".git"
        if dotgit.is_file():
            target = dotgit.read_text(errors="replace").removeprefix("gitdir:").strip()
            if not os.path.realpath(target).startswith(os.path.realpath(common) + os.sep):
                continue   # worktree di un altro repo
        orphans.append(p)
    return orphans


def processes_inside(paths: list[Path]) -> set[Path]:
    """Worktree con almeno un processo che ci ha la cwd (lsof; senza lsof: tutti occupati)."""
    if not paths:
        return set()
    try:
        listing = subprocess.run(
            ["lsof", "-a", "-d", "cwd", "-Fn", "-w"], capture_output=True, text=True, timeout=20,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return set(paths)
    cwds = [os.path.realpath(ln[1:]) for ln in listing.splitlines() if ln.startswith("n")]
    busy = set()
    for path in paths:
        root = os.path.realpath(path)
        if any(c == root or c.startswith(root + os.sep) for c in cwds):
            busy.add(path)
    return busy


def ago(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 3600:
        return f"{seconds // 60} min"
    if seconds < 2 * 86400:
        return f"{seconds // 3600} h"
    return f"{seconds // 86400} giorni"


def plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def short(path: Path, primary: Path) -> str:
    try:
        return str(path.relative_to(primary.parent))
    except ValueError:
        return str(path)


@dataclass
class Report:
    primary: Worktree
    trees: list[Worktree]
    branches: list[Branch]
    remotes: list[Branch]
    orphans: list[Path]
    stashes: int
    primary_dirty: list[str]

    @property
    def silent(self) -> bool:
        return not (
            self.trees or self.branches or self.remotes or self.orphans or self.stashes
            or self.primary_dirty or self.primary.branch != "main"
        )


def build_report(now: float) -> Report:
    reset_caches()
    common = common_dir()
    all_trees = list_worktrees()
    primary, trees = all_trees[0], all_trees[1:]
    for wt in trees:
        try:
            inspect(wt, now, common)
        except Exception as exc:  # un worktree strano non deve zittire gli altri
            wt.state, wt.removable, wt.why_kept = "error", False, str(exc)[:200]
    primary_status = git("status", "--porcelain=v1", "-z", cwd=primary.path).stdout
    return Report(
        primary=primary,
        trees=trees,
        branches=stray_branches(all_trees, common),
        remotes=remote_branches(common),
        orphans=orphan_dirs(all_trees, common),
        stashes=len(out("stash", "list").splitlines()),
        primary_dirty=parse_status(primary_status)[0],
    )


STATE_TEXT = {"active": "IN CORSO", "stale": "FERMO", "merged": "SU MAIN", "empty": "VUOTO", "missing": "SPARITO",
              "error": "ERRORE"}
FORGOTTEN = " — lavoro dimenticato? dillo a Daniele e decidete insieme (lezione B350)"


def render(report: Report, now: float) -> list[str]:
    p = report.primary.path
    lines: list[str] = []
    if report.primary.branch != "main" or report.primary_dirty:
        what = []
        if report.primary.branch != "main":
            what.append(f"è su {report.primary.branch or 'detached HEAD'}, non su main")
        if report.primary_dirty:
            what.append(plural(len(report.primary_dirty), "file modificato o nuovo", "file modificati o nuovi"))
        lines.append(f"⚠️  worktree primario: {'; '.join(what)} — se non è tuo, è di un'altra sessione: lavora in un worktree.")
    for wt in report.trees:
        head = f"{STATE_TEXT[wt.state]:<8} {short(wt.path, p)}  [{wt.label}]"
        if wt.state == "missing":
            if wt.lost:
                after = (f"il suo reflog ha {plural(len(wt.lost), 'commit', 'commit')} non su main "
                         f"({', '.join(s[:7] for s in wt.lost[:3])}): recuperali prima di `git worktree prune`")
            else:
                after = "nessun commit perso con `git worktree prune`"
            lines.append(f"{head} — la cartella non c'è più: se l'hai spostata `git worktree repair <nuovo path>`; {after}")
            continue
        if wt.state == "error":
            lines.append(f"{head} — non riesco a leggerlo ({wt.why_kept}): guardalo a mano")
            continue
        idle = ago(now - wt.last_activity)
        if wt.state in ("active", "stale"):
            bits = []
            if wt.operation:
                bits.append(f"{wt.operation} in corso")
            if wt.unmerged:
                bits.append(plural(wt.unmerged, "commit non su main", "commit non su main"))
            if wt.dirty:
                bits.append(plural(len(wt.dirty), "file non committato", "file non committati"))
            if wt.hidden:
                bits.append(plural(len(wt.hidden), "file nascosto a git", "file nascosti a git"))
            if wt.lost:
                bits.append(f"{plural(len(wt.lost), 'commit', 'commit')} nella storia o nei reflog non su main "
                            f"({', '.join(s[:7] for s in wt.lost[:3])})")
            detail = f"{', '.join(bits)}, toccato {idle} fa"
            if wt.state == "stale":
                detail += FORGOTTEN
            lines.append(f"{head} — {detail}")
        elif wt.removable:
            lines.append(f"{head} — nessun lavoro perso a toglierlo: `python scripts/worktrees.py --clean`")
        else:
            lines.append(f"{head} — resta: {wt.why_kept}")
    for br in report.branches:
        if br.unmerged:
            idle = now - br.last_activity
            lines.append(f"BRANCH   {br.name} — {plural(br.unmerged, 'commit', 'commit')} non su main e nessun worktree "
                         f"(toccato {ago(idle)} fa)" + (FORGOTTEN if idle >= STALE_IDLE_S else ""))
        else:
            lines.append(f"BRANCH   {br.name} — già su main: `python scripts/worktrees.py --clean`")
    for br in report.remotes:
        if br.unmerged:
            idle = now - br.committed
            lines.append(f"REMOTO   {br.name} — {plural(br.unmerged, 'commit', 'commit')} non su main "
                         f"(ultimo commit {ago(idle)} fa)" + (FORGOTTEN if idle >= STALE_IDLE_S else ""))
        else:
            name = br.name.removeprefix("origin/")
            lines.append(f"REMOTO   {br.name} — già su main: si può cancellare con l'OK di Daniele "
                         f"(`git push origin --delete {name}`)")
    for orphan in report.orphans:
        lines.append(f"CARTELLA {short(orphan, p)} — sembra un worktree ma git non lo conosce: guardaci e cancellala a mano")
    if report.stashes:
        lines.append(f"STASH    {report.stashes} — `git stash list`: sono condivisi fra le sessioni, guardali prima di toglierli")
    return lines


# ── pulizia ──────────────────────────────────────────────────────────────────


def recheck(wt: Worktree) -> Worktree | None:
    """Lo stesso worktree riletto da capo, subito prima di toglierlo."""
    for fresh in list_worktrees()[1:]:
        if os.path.realpath(fresh.path) == os.path.realpath(wt.path):
            reset_caches()
            inspect(fresh, time.time(), common_dir())
            return fresh
    return None


def clean(report: Report, dry_run: bool, now: float) -> list[str]:
    done: list[str] = []
    p = report.primary.path
    try:
        here = os.path.realpath(Path.cwd())
    except OSError:
        here = ""
    candidates = [wt for wt in report.trees if wt.removable]
    busy = processes_inside([wt.path for wt in candidates])
    for wt in candidates:
        root = os.path.realpath(wt.path)
        if wt.path in busy or here == root or here.startswith(root + os.sep):
            done.append(f"resta    {short(wt.path, p)} — c'è un processo dentro")
            continue
        if dry_run:
            done.append(f"toglierei {short(wt.path, p)}")
            if wt.branch:
                done.append(f"toglierei branch {wt.branch}")
            continue
        fresh = recheck(wt)
        if fresh is None or not fresh.removable or fresh.head != wt.head or fresh.branch != wt.branch:
            done.append(f"resta    {short(wt.path, p)} — è cambiato durante la pulizia")
            continue
        result = git("worktree", "remove", str(wt.path), cwd=p)
        if result.returncode != 0:
            done.append(f"resta    {short(wt.path, p)} — {result.stderr.strip()}")
            continue
        done.append(f"tolto    {short(wt.path, p)}")
        if wt.branch:
            done.append(delete_branch(wt.branch, wt.head, dry_run))
    for br in report.branches:
        if br.unmerged or br.name == "main":
            continue
        if now - br.last_activity < BRANCH_IDLE_S:
            done.append(f"resta    branch {br.name} — toccato {ago(now - br.last_activity)} fa")
            continue
        if not dry_run:
            reset_caches()
            common = common_dir()
            if br.name in busy_branches(list_worktrees()) or branch_unmerged(br.sha, common / "logs" / "refs" / "heads" / br.name):
                done.append(f"resta    branch {br.name} — è cambiato durante la pulizia")
                continue
        done.append(delete_branch(br.name, br.sha, dry_run))
    return done


def delete_branch(name: str, sha: str, dry_run: bool) -> str:
    if name == "main":
        return "resta    branch main"
    if dry_run:
        return f"toglierei branch {name}"
    # update-ref con il valore atteso: se nel frattempo il branch si è mosso, resta.
    result = git("update-ref", "-d", f"refs/heads/{name}", sha)
    if result.returncode != 0:
        return f"resta    branch {name} — {result.stderr.strip()}"
    return f"tolto    branch {name}"


def fetch_origin(dry_run: bool) -> tuple[bool, list[str]]:
    """Fetch senza --prune: un branch remoto cancellato su origin sparisce solo se era già su main."""
    preview = git("fetch", "--prune", "--dry-run", "origin")
    if preview.returncode != 0:
        return False, [preview.stderr.strip()]
    fetched = git("-c", "fetch.prune=false", "-c", "remote.origin.prune=false", "fetch", "origin")
    if fetched.returncode != 0:
        return False, [fetched.stderr.strip()]
    notes = []
    for line in preview.stderr.splitlines():
        match = re.search(r"\[deleted\].*->\s+(origin/\S+)", line)
        if not match:
            continue
        ref = f"refs/remotes/{match.group(1)}"
        sha = git("rev-parse", "--verify", "--quiet", ref).stdout.strip()
        if not sha:
            continue
        local_log = common_dir() / "logs" / "refs" / "heads" / match.group(1).removeprefix("origin/")
        if not branch_unmerged(sha, common_dir() / "logs" / ref, local_log):
            if not dry_run:
                git("update-ref", "-d", ref, sha)
            notes.append(f"{'toglierei' if dry_run else 'tolto':<8} {match.group(1)} (cancellato su origin, già su main)")
        else:
            notes.append(f"resta    {match.group(1)} — cancellato su origin ma con commit non su main: "
                         "è l'unica copia, guardalo prima di `git fetch --prune`")
    return True, notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quiet", action="store_true", help="niente output se non c'è niente da segnalare")
    parser.add_argument("--clean", action="store_true", help="fetch di origin, poi toglie ciò che è già su main")
    parser.add_argument("--dry-run", action="store_true", help="con --clean: elenca soltanto")
    parser.add_argument("--pushing-main", metavar="SHA", action="append", default=[],
                        help="(pre-push) commit che il push sta mettendo su main: nel report conta già come su main")
    args = parser.parse_args(argv)
    if args.pushing_main and args.clean:
        parser.error("--pushing-main vale solo per il report, mai con --clean")
    ASSUMED_ON_MAIN[:] = [sha for sha in args.pushing_main if sha.strip("0")]

    if git("rev-parse", "--git-dir").returncode != 0:
        return 0
    notes: list[str] = []
    if args.clean:
        ok, notes = fetch_origin(args.dry_run)
        if not ok:
            print("✗ fetch di origin fallito, non tolgo niente su dati vecchi:\n" + "\n".join(notes))
            return 1
    if git("rev-parse", "--verify", "--quiet", BASE).returncode != 0:
        if not args.quiet:
            print(f"✗ {BASE_LABEL} non esiste: niente da confrontare.")
        return 0

    now = time.time()
    report = build_report(now)
    if args.clean:
        actions = notes + clean(report, args.dry_run, now)
        print("\n".join(actions) if actions else "Niente da togliere.")
        if args.dry_run:
            return 0
        if actions:
            now = time.time()
            report = build_report(now)
    if report.silent:
        if not args.quiet:
            print("✅ Solo il worktree primario, su main e pulito. Nessun branch o stash in giro.")
        return 0
    lines = render(report, now)
    if lines:
        print("Worktree e branch (python scripts/worktrees.py):")
        print("\n".join(f"  {ln}" for ln in lines))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # gli hook non devono mai rompere una sessione o un push
        print(f"worktrees.py: {exc}", file=sys.stderr)
        sys.exit(0)
