"""D286 — `scripts/worktrees.py`: report dei worktree residui e pulizia sicura.

Ogni test costruisce un repo vero in tmp_path (origin bare + clone primario con
lo script committato) e lancia lo script come lo lanciano gli hook. Il punto
che conta è il lato «mai»: un worktree con lavoro non su origin/main, appena
toccato, bloccato, con un processo dentro o con file ignorati non rigenerabili
non si tocca. L'età si simula spostando indietro le mtime, come la legge lo
script.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "worktrees.py"

_spec = importlib.util.spec_from_file_location("d286_worktrees", SCRIPT)
wtmod = importlib.util.module_from_spec(_spec)
sys.modules["d286_worktrees"] = wtmod
_spec.loader.exec_module(wtmod)  # type: ignore[union-attr]

HOUR = 3600
DAY = 24 * HOUR
needs_lsof = pytest.mark.skipif(shutil.which("lsof") is None, reason="--clean richiede lsof")


@pytest.fixture
def env(tmp_path, monkeypatch):
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("")
    for key, value in {
        "GIT_CONFIG_GLOBAL": str(gitconfig), "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("GIT_DIR", raising=False)
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)
    return tmp_path


def run(*args, cwd):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, f"{args}: {result.stderr}"
    return result.stdout.strip()


def g(cwd, *args):
    return run("git", *args, cwd=cwd)


@pytest.fixture
def repo(env):
    """origin bare + primario `proj` su main, con lo script e un .gitignore come quello vero."""
    base = env / "work"
    base.mkdir()
    g(base, "init", "-q", "--bare", "-b", "main", "origin.git")
    g(base, "clone", "-q", "origin.git", "proj")
    prim = base / "proj"
    (prim / "scripts").mkdir()
    shutil.copy(SCRIPT, prim / "scripts" / "worktrees.py")
    (prim / ".gitignore").write_text("node_modules/\n.next/\n__pycache__/\nreports/\n.env\n")
    (prim / "app.txt").write_text("v1\n")
    g(prim, "checkout", "-q", "-b", "main")
    g(prim, "add", "-A")
    g(prim, "commit", "-q", "-m", "init")
    g(prim, "push", "-q", "-u", "origin", "main")
    return prim


def script(prim, *args, check=True):
    result = subprocess.run(
        [sys.executable, str(prim / "scripts" / "worktrees.py"), *args],
        cwd=prim, capture_output=True, text=True,
    )
    if check:
        assert result.returncode == 0, result.stderr
    return result


def add_worktree(prim, name, branch=None):
    path = prim.parent / f"proj-{name}"
    if branch:
        g(prim, "worktree", "add", "-q", str(path), "-b", branch, "origin/main")
    else:
        g(prim, "worktree", "add", "-q", "--detach", str(path), "origin/main")
    return path


def commit(path, name="feature.txt", text="x\n", msg="work"):
    (path / name).write_text(text)
    g(path, "add", name)
    g(path, "commit", "-q", "-m", msg)


def push_to_main(path):
    g(path, "push", "-q", "origin", "HEAD:main")
    g(path, "fetch", "-q", "origin")


def age(prim, wt_path, branch, seconds):
    """Porta indietro di `seconds` tutto ciò che lo script legge come attività."""
    when = time.time() - seconds
    common = Path(g(prim, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    gitdir = common / "worktrees" / wt_path.name
    targets = [wt_path, gitdir]
    if branch:
        targets.append(common / "logs" / "refs" / "heads" / branch)
    for target in targets:
        if not target.exists():
            continue
        for root, dirs, files in os.walk(target, topdown=False):
            for item in files + dirs:
                os.utime(os.path.join(root, item), (when, when), follow_symlinks=False)
        os.utime(target, (when, when))


def has_branch(prim, name):
    return subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{name}"], cwd=prim,
    ).returncode == 0


# ── report ──────────────────────────────────────────────────────────────────


def test_quiet_is_silent_when_only_the_primary_exists(repo):
    assert script(repo, "--quiet").stdout == ""
    assert "Solo il worktree primario" in script(repo).stdout


def test_active_worktree_is_reported_in_quiet_mode(repo):
    wt = add_worktree(repo, "b1", "brief/B1-x")
    (wt / "app.txt").write_text("changed\n")
    out = script(repo, "--quiet").stdout
    assert "IN CORSO" in out and "proj-b1" in out and "1 file non committato" in out


def test_unmerged_work_idle_for_days_is_flagged_as_forgotten(repo):
    wt = add_worktree(repo, "b2", "brief/B2-x")
    commit(wt)
    age(repo, wt, "brief/B2-x", 5 * DAY)
    out = script(repo, "--quiet").stdout
    assert "FERMO" in out and "1 commit non su main" in out and "B350" in out


def test_primary_off_main_or_dirty_is_reported(repo):
    (repo / "stray.txt").write_text("?")
    out = script(repo, "--quiet").stdout
    assert "worktree primario" in out and "1 file modificato o nuovo" in out


def test_report_never_rewrites_another_sessions_index(repo):
    wt = add_worktree(repo, "b3", "brief/B3-x")
    # Stat cambiata senza cambiare il contenuto: un `git status` normale riscriverebbe l'index.
    later = time.time() + 5
    os.utime(wt / "app.txt", (later, later))
    index = Path(g(wt, "rev-parse", "--absolute-git-dir")) / "index"
    before = (index.stat().st_mtime_ns, index.read_bytes())
    script(repo)
    assert (index.stat().st_mtime_ns, index.read_bytes()) == before


def test_orphan_dir_stash_and_remote_branch_are_reported_not_touched(repo):
    orphan = repo.parent / "proj-old"
    orphan.mkdir()
    (repo / "app.txt").write_text("stash me\n")
    g(repo, "stash", "-q")
    g(repo, "push", "-q", "origin", "main:brief/R1-merged")
    g(repo, "fetch", "-q", "origin")
    out = script(repo, "--quiet").stdout
    assert "CARTELLA proj-old" in out
    assert "STASH    1" in out
    assert "git push origin --delete brief/R1-merged" in out
    script(repo, "--clean")
    assert orphan.is_dir()
    assert g(repo, "stash", "list")
    assert "brief/R1-merged" in g(repo, "ls-remote", "--heads", "origin")


def test_not_a_git_repo_exits_zero_and_quiet(env):
    lone = env / "lone"
    (lone / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, lone / "scripts" / "worktrees.py")
    result = script(lone, "--quiet")
    assert result.stdout == ""


# ── clean: cosa toglie ──────────────────────────────────────────────────────


@needs_lsof
def test_merged_and_idle_worktree_is_removed_with_its_branch(repo):
    wt = add_worktree(repo, "a1", "brief/A1-x")
    commit(wt)
    push_to_main(wt)
    age(repo, wt, "brief/A1-x", 3 * HOUR)
    assert "SU MAIN" in script(repo).stdout
    out = script(repo, "--clean").stdout
    assert "tolto    proj-a1" in out and "tolto    branch brief/A1-x" in out
    assert not wt.exists() and not has_branch(repo, "brief/A1-x")
    assert script(repo, "--quiet").stdout == ""


@needs_lsof
def test_cherry_picked_commit_counts_as_merged(repo):
    wt = add_worktree(repo, "a2", "brief/A2-x")
    commit(wt, msg="feature")
    sha = g(wt, "rev-parse", "HEAD")
    commit(repo, name="other.txt", msg="main moved on")
    g(repo, "cherry-pick", sha)
    g(repo, "push", "-q", "origin", "main")
    assert g(repo, "rev-parse", "HEAD") != sha
    age(repo, wt, "brief/A2-x", 3 * HOUR)
    script(repo, "--clean")
    assert not wt.exists() and not has_branch(repo, "brief/A2-x")


@needs_lsof
def test_regenerable_ignored_files_do_not_block_removal(repo):
    wt = add_worktree(repo, "a3", "brief/A3-x")
    commit(wt)
    push_to_main(wt)
    (wt / "node_modules" / "pkg").mkdir(parents=True)
    (wt / "node_modules" / "pkg" / "index.js").write_text("")
    (wt / ".next").mkdir()
    age(repo, wt, "brief/A3-x", 3 * HOUR)
    script(repo, "--clean")
    assert not wt.exists()


@needs_lsof
def test_detached_merged_worktree_is_removed(repo):
    wt = add_worktree(repo, "a4")
    commit(wt)
    push_to_main(wt)
    age(repo, wt, None, 3 * HOUR)
    out = script(repo, "--clean").stdout
    assert "tolto    proj-a4" in out and not wt.exists()


@needs_lsof
def test_empty_worktree_is_kept_for_a_day_then_removed(repo):
    wt = add_worktree(repo, "a5", "brief/A5-x")
    age(repo, wt, "brief/A5-x", 3 * HOUR)
    out = script(repo, "--clean").stdout
    assert "Niente da togliere" in out and wt.exists()
    assert "VUOTO" in script(repo).stdout
    age(repo, wt, "brief/A5-x", 2 * DAY)
    script(repo, "--clean")
    assert not wt.exists() and not has_branch(repo, "brief/A5-x")


@needs_lsof
def test_stray_branches_merged_go_unmerged_stay(repo):
    g(repo, "branch", "brief/M1-done", "origin/main")
    wt = add_worktree(repo, "tmp", "brief/U1-wip")
    commit(wt)
    g(repo, "worktree", "remove", str(wt))
    out = script(repo).stdout
    assert "BRANCH   brief/U1-wip — 1 commit non su main" in out
    assert "BRANCH   brief/M1-done — già su main" in out
    common = Path(g(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    old = time.time() - 3 * HOUR
    os.utime(common / "logs" / "refs" / "heads" / "brief" / "M1-done", (old, old))
    script(repo, "--clean")
    assert not has_branch(repo, "brief/M1-done")
    assert has_branch(repo, "brief/U1-wip")


@needs_lsof
def test_missing_worktree_is_only_reported_never_pruned(repo):
    """Spostato con mv o su un disco non montato: `prune` cancellerebbe index e commit detached."""
    wt = add_worktree(repo, "gone", "brief/G1-x")
    shutil.move(str(wt), str(repo.parent / "moved-away"))
    out = script(repo).stdout
    assert "SPARITO" in out and "git worktree repair" in out
    script(repo, "--clean")
    assert "proj-gone" in g(repo, "worktree", "list")


# ── clean: cosa NON toglie mai ──────────────────────────────────────────────


@needs_lsof
def test_merged_but_recently_touched_is_kept(repo):
    wt = add_worktree(repo, "k1", "brief/K1-x")
    commit(wt)
    push_to_main(wt)
    out = script(repo, "--clean").stdout
    assert "Niente da togliere" in out and wt.exists()
    assert "resta: toccato" in script(repo).stdout


@needs_lsof
@pytest.mark.parametrize("make_dirty", [
    lambda wt: (wt / "app.txt").write_text("edited\n"),
    lambda wt: (wt / "new_untracked.txt").write_text("new\n"),
    lambda wt: (g(wt, "rm", "-q", "--cached", "app.txt")),
])
def test_dirty_worktree_is_never_removed_even_when_old(repo, make_dirty):
    wt = add_worktree(repo, "k2", "brief/K2-x")
    commit(wt)
    push_to_main(wt)
    make_dirty(wt)
    age(repo, wt, "brief/K2-x", 30 * DAY)
    script(repo, "--clean")
    assert wt.exists() and has_branch(repo, "brief/K2-x")
    assert "FERMO" in script(repo).stdout


@needs_lsof
def test_unpushed_commit_is_never_removed(repo):
    wt = add_worktree(repo, "k3", "brief/K3-x")
    commit(wt)
    age(repo, wt, "brief/K3-x", 30 * DAY)
    script(repo, "--clean")
    assert wt.exists() and has_branch(repo, "brief/K3-x")


@needs_lsof
def test_squash_merge_counts_as_merged_by_content(repo):
    wt = add_worktree(repo, "k4", "brief/K4-x")
    commit(wt, name="a.txt")
    commit(wt, name="b.txt")
    g(repo, "merge", "-q", "--squash", "brief/K4-x")
    g(repo, "commit", "-q", "-m", "squash")
    g(repo, "push", "-q", "origin", "main")
    g(repo, "fetch", "-q", "origin")
    age(repo, wt, "brief/K4-x", 3 * HOUR)
    script(repo, "--clean")
    assert not wt.exists() and not has_branch(repo, "brief/K4-x")


@needs_lsof
def test_non_regenerable_ignored_files_block_removal(repo):
    wt = add_worktree(repo, "k5", "brief/K5-x")
    commit(wt)
    push_to_main(wt)
    (wt / "reports").mkdir()
    (wt / "reports" / "result.json").write_text("{}")
    (wt / ".env").write_text("SECRET=1")
    age(repo, wt, "brief/K5-x", 2 * DAY)
    script(repo, "--clean")
    assert (wt / "reports" / "result.json").exists() and (wt / ".env").exists()
    out = script(repo).stdout
    assert "file ignorati da guardare" in out and "reports/" in out and ".env" in out


@needs_lsof
def test_locked_worktree_is_kept(repo):
    wt = add_worktree(repo, "k6", "brief/K6-x")
    commit(wt)
    push_to_main(wt)
    g(repo, "worktree", "lock", str(wt))
    age(repo, wt, "brief/K6-x", 2 * DAY)
    script(repo, "--clean")
    assert wt.exists()
    assert "bloccato" in script(repo).stdout


@needs_lsof
def test_worktree_with_a_process_inside_is_kept(repo):
    wt = add_worktree(repo, "k7", "brief/K7-x")
    commit(wt)
    push_to_main(wt)
    age(repo, wt, "brief/K7-x", 2 * DAY)
    proc = subprocess.Popen(["sleep", "30"], cwd=wt / "scripts")
    try:
        out = script(repo, "--clean").stdout
    finally:
        proc.kill()
        proc.wait()
    assert wt.exists() and "c'è un processo dentro" in out


@needs_lsof
def test_dry_run_changes_nothing(repo):
    wt = add_worktree(repo, "k8", "brief/K8-x")
    commit(wt)
    push_to_main(wt)
    age(repo, wt, "brief/K8-x", 3 * HOUR)
    out = script(repo, "--clean", "--dry-run").stdout
    assert "toglierei proj-k8" in out and "toglierei branch brief/K8-x" in out
    assert wt.exists() and has_branch(repo, "brief/K8-x")


def test_failed_fetch_aborts_clean(repo):
    wt = add_worktree(repo, "k9", "brief/K9-x")
    commit(wt)
    push_to_main(wt)
    age(repo, wt, "brief/K9-x", 3 * HOUR)
    g(repo, "remote", "set-url", "origin", str(repo.parent / "nowhere.git"))
    result = script(repo, "--clean", check=False)
    assert result.returncode == 1 and "fetch di origin fallito" in result.stdout
    assert wt.exists()


def test_branch_moved_after_the_check_is_not_deleted(repo, monkeypatch):
    g(repo, "branch", "brief/R2-x", "origin/main")
    old = g(repo, "rev-parse", "brief/R2-x")
    commit(repo, name="later.txt")
    g(repo, "branch", "-f", "brief/R2-x", "HEAD")
    monkeypatch.setattr(wtmod, "REPO_ROOT", repo)
    assert wtmod.delete_branch("brief/R2-x", old, dry_run=False).startswith("resta")
    assert has_branch(repo, "brief/R2-x")


def test_primary_is_never_a_candidate(repo, monkeypatch):
    monkeypatch.setattr(wtmod, "REPO_ROOT", repo)
    report = wtmod.build_report(time.time() + 365 * DAY)
    assert report.primary.path.resolve() == repo.resolve()
    assert all(wt.path.resolve() != repo.resolve() for wt in report.trees)


@pytest.mark.parametrize("rel,expected", [
    ("frontend/node_modules/", True),
    ("node_modules/", True),
    ("frontend/.next/", True),
    ("backend/engine/__pycache__/", True),
    ("backend/x.pyc", True),
    (".pytest_cache/", True),
    ("frontend/tsconfig.tsbuildinfo", True),
    ("frontend/public/sw.js", True),
    ("frontend/.vercel/", True),
    ("docs/.DS_Store", True),
    (".env", False),
    ("frontend/.env.local", False),
    ("reports/", False),
    ("out/", False),
    ("output/", False),
    ("tmp/", False),
    ("_backups/", False),
    ("backend/data/logs/", False),
    ("AGENTS.md", False),
])
def test_regenerable_allowlist(rel, expected):
    assert wtmod.is_regenerable(rel) is expected


# ── revisione avversariale: ogni difetto confermato ha il suo test ──────────


def merged_old_worktree(repo, name, branch="auto"):
    """Worktree con un commit già su origin/main, fermo da 3 ore: il caso «da togliere»."""
    branch = f"brief/{name.upper()}-x" if branch == "auto" else branch
    wt = add_worktree(repo, name, branch)
    commit(wt, name=f"{name}.txt")
    push_to_main(wt)
    return wt, branch


@needs_lsof
def test_show_untracked_files_no_cannot_hide_files(repo):
    """Con status.showUntrackedFiles=no anche `git worktree remove` non vede i non tracciati."""
    wt, branch = merged_old_worktree(repo, "r1")
    (wt / "notes.md").write_text("lavoro non salvato")
    (wt / ".env").write_text("SECRET=1")
    g(repo, "config", "status.showUntrackedFiles", "no")
    age(repo, wt, branch, 3 * DAY)
    script(repo, "--clean")
    assert (wt / "notes.md").exists() and (wt / ".env").exists()
    assert "1 file non committato" in script(repo).stdout


@needs_lsof
@pytest.mark.parametrize("flag", ["--skip-worktree", "--assume-unchanged"])
def test_edits_hidden_from_git_block_removal(repo, flag):
    wt, branch = merged_old_worktree(repo, "r2")
    (wt / "app.txt").write_text("override locale\n")
    g(wt, "update-index", flag, "app.txt")
    assert g(wt, "status", "--porcelain") == ""
    age(repo, wt, branch, 3 * DAY)
    script(repo, "--clean")
    assert (wt / "app.txt").read_text() == "override locale\n"
    assert "file nascosto a git" in script(repo).stdout


@needs_lsof
def test_commit_left_only_in_the_reflog_blocks_removal(repo):
    wt, branch = merged_old_worktree(repo, "r3")
    commit(wt, name="lost.txt", msg="lavoro poi resettato")
    lost = g(wt, "rev-parse", "HEAD")
    g(wt, "reset", "-q", "--hard", "origin/main")
    age(repo, wt, branch, 3 * DAY)
    script(repo, "--clean")
    assert wt.exists()
    out = script(repo).stdout
    assert "FERMO" in out and f"nella storia o nei reflog non su main ({lost[:7]})" in out


@needs_lsof
def test_detached_commit_left_behind_by_checkout_blocks_removal(repo):
    wt = add_worktree(repo, "r4")
    commit(wt, name="detached.txt")
    g(wt, "checkout", "-q", "--detach", "origin/main")
    commit(repo, name="later.txt", msg="main va avanti")
    g(repo, "push", "-q", "origin", "main")
    g(wt, "fetch", "-q", "origin")
    g(wt, "checkout", "-q", "--detach", "origin/main")
    age(repo, wt, None, 30 * DAY)
    script(repo, "--clean")
    assert wt.exists()


@needs_lsof
def test_content_only_in_a_merge_commit_is_not_on_main(repo):
    """`git cherry` salta i merge: una correzione dentro il merge commit non è su main."""
    wt = add_worktree(repo, "r5", "brief/R5-x")
    commit(wt, name="feature.txt", msg="feature")
    feature = g(wt, "rev-parse", "HEAD")
    commit(repo, name="other.txt", msg="main va avanti")
    g(repo, "push", "-q", "origin", "main")
    g(wt, "fetch", "-q", "origin")
    g(wt, "merge", "-q", "--no-ff", "--no-commit", "origin/main")
    (wt / "fix.txt").write_text("correzione fatta nel merge\n")
    g(wt, "add", "fix.txt")
    g(wt, "commit", "-q", "-m", "merge con correzione")
    g(repo, "cherry-pick", feature)
    g(repo, "push", "-q", "origin", "main")
    g(repo, "fetch", "-q", "origin")
    age(repo, wt, "brief/R5-x", 30 * DAY)
    assert "FERMO" in script(repo).stdout
    script(repo, "--clean")
    assert (wt / "fix.txt").exists() and has_branch(repo, "brief/R5-x")


@needs_lsof
def test_whitespace_only_fix_is_not_on_main(repo):
    """I patch-id ignorano gli spazi: un'indentazione corretta in Python cambia il programma."""
    wt = add_worktree(repo, "r6", "brief/R6-x")
    (wt / "f.py").write_text("for x in y:\n    pass\n    return None\n")
    g(wt, "add", "f.py")
    g(wt, "commit", "-q", "-m", "f")
    g(repo, "cherry-pick", g(wt, "rev-parse", "HEAD"))
    g(repo, "push", "-q", "origin", "main")
    g(repo, "fetch", "-q", "origin")
    (wt / "f.py").write_text("for x in y:\n    pass\nreturn None\n")
    g(wt, "commit", "-q", "-a", "--amend", "-m", "f (indentazione corretta)")
    age(repo, wt, "brief/R6-x", 30 * DAY)
    script(repo, "--clean")
    assert wt.exists() and "return None\n" in (wt / "f.py").read_text()


def test_hook_environment_does_not_leak_into_other_worktrees(repo):
    """Nel pre-push git esporta GIT_DIR del worktree che pusha: lo script non deve usarlo."""
    pusher = add_worktree(repo, "r7a", "brief/R7A-x")
    other, _ = merged_old_worktree(repo, "r7b")
    (pusher / "only-in-pusher.txt").write_text("x")
    g(pusher, "add", "only-in-pusher.txt")
    pusher_gitdir = g(pusher, "rev-parse", "--absolute-git-dir")
    result = subprocess.run(
        [sys.executable, str(repo / "scripts" / "worktrees.py")],
        cwd=pusher, capture_output=True, text=True,
        env={**os.environ, "GIT_DIR": pusher_gitdir, "GIT_INDEX_FILE": str(Path(pusher_gitdir) / "index")},
    )
    out = result.stdout
    assert "worktree primario" not in out, out
    line = next(ln for ln in out.splitlines() if "proj-r7b" in ln)
    assert "SU MAIN" in line, out


@needs_lsof
def test_empty_worktree_updated_by_fast_forward_stays_empty(repo):
    """Un pull/ff a un main più nuovo non è un commit: soglia di 24 h, non di 2."""
    wt = add_worktree(repo, "r8", "brief/R8-x")
    commit(repo, name="later.txt", msg="main va avanti")
    g(repo, "push", "-q", "origin", "main")
    g(wt, "fetch", "-q", "origin")
    g(wt, "merge", "-q", "--ff-only", "origin/main")
    age(repo, wt, "brief/R8-x", 3 * HOUR)
    assert "VUOTO" in script(repo).stdout
    script(repo, "--clean")
    assert wt.exists()


@needs_lsof
def test_rebase_in_progress_is_never_removed_and_its_branch_is_busy(repo):
    wt = add_worktree(repo, "r9", "brief/R9-x")
    (wt / "app.txt").write_text("branch\n")
    g(wt, "commit", "-q", "-a", "-m", "branch side")
    (repo / "app.txt").write_text("main\n")
    g(repo, "commit", "-q", "-a", "-m", "main side")
    g(repo, "push", "-q", "origin", "main")
    g(wt, "fetch", "-q", "origin")
    subprocess.run(["git", "rebase", "origin/main"], cwd=wt, capture_output=True)
    (wt / "app.txt").write_text("main\n")
    g(wt, "add", "app.txt")
    age(repo, wt, None, 30 * DAY)
    out = script(repo).stdout
    assert "rebase in corso" in out and "rebase di brief/R9-x" in out
    assert "BRANCH   brief/R9-x" not in out
    script(repo, "--clean")
    assert wt.exists() and has_branch(repo, "brief/R9-x")


def test_independent_sibling_repo_is_not_an_orphan(repo):
    sibling = repo.parent / "proj-coach"
    sibling.mkdir()
    g(sibling, "init", "-q")
    leftover = repo.parent / "proj-leftover"
    leftover.mkdir()
    out = script(repo, "--quiet").stdout
    assert "proj-coach" not in out
    assert "CARTELLA proj-leftover" in out


@needs_lsof
def test_local_branch_named_origin_main_does_not_fake_merged(repo):
    wt = add_worktree(repo, "r10", "brief/R10-x")
    commit(wt, name="unpushed.txt")
    g(wt, "branch", "origin/main")   # stesso nome corto del remoto
    age(repo, wt, "brief/R10-x", 30 * DAY)
    script(repo, "--clean")
    assert wt.exists() and has_branch(repo, "brief/R10-x")


@needs_lsof
def test_branch_deleted_on_origin_is_pruned_locally_only_when_on_main(repo):
    origin = repo.parent / "origin.git"
    g(repo, "push", "-q", "origin", "main:brief/D1-merged")
    side = add_worktree(repo, "side", "brief/D2-wip")
    commit(side, name="wip.txt")
    g(side, "push", "-q", "origin", "HEAD:brief/D2-wip")
    g(repo, "worktree", "remove", "--force", str(side))
    g(repo, "branch", "-D", "brief/D2-wip")
    g(repo, "fetch", "-q", "origin")
    g(origin, "branch", "-D", "brief/D1-merged", "brief/D2-wip")
    out = script(repo, "--clean").stdout
    assert "tolto    origin/brief/D1-merged" in out
    assert "resta    origin/brief/D2-wip" in out
    refs = g(repo, "for-each-ref", "--format=%(refname)", "refs/remotes/origin")
    assert "refs/remotes/origin/brief/D1-merged" not in refs
    assert "refs/remotes/origin/brief/D2-wip" in refs


@needs_lsof
def test_main_checked_out_in_a_secondary_worktree_is_never_removed(repo):
    g(repo, "checkout", "-q", "-b", "elsewhere")
    wt = repo.parent / "proj-main"
    g(repo, "worktree", "add", "-q", str(wt), "main")
    age(repo, wt, "main", 30 * DAY)
    script(repo, "--clean")
    assert wt.exists() and has_branch(repo, "main")


@needs_lsof
def test_stray_merged_branch_touched_recently_is_kept(repo):
    g(repo, "branch", "salvage/abc", "origin/main")
    out = script(repo, "--clean").stdout
    assert "resta    branch salvage/abc" in out and has_branch(repo, "salvage/abc")


def test_untracked_dir_activity_reads_the_files_inside(repo):
    wt = add_worktree(repo, "r11", "brief/R11-x")
    (wt / "newdir").mkdir()
    (wt / "newdir" / "a.txt").write_text("old")
    age(repo, wt, "brief/R11-x", 5 * DAY)
    (wt / "newdir" / "a.txt").write_text("edited now")   # la mtime della cartella non cambia
    out = script(repo).stdout
    line = next(ln for ln in out.splitlines() if "proj-r11" in ln)
    assert "IN CORSO" in line and "toccato 0 min fa" in line


# ── revisione avversariale, secondo giro ────────────────────────────────────


def test_parked_work_reverted_on_a_stray_branch_is_not_deleted(repo):
    """Commit + revert: la punta è «uguale a main», ma il lavoro esiste solo nella storia del branch."""
    wt = add_worktree(repo, "p1", "brief/P1-x")
    commit(wt, name="feature.py", msg="feature")
    g(wt, "revert", "--no-edit", "HEAD")
    g(repo, "worktree", "remove", str(wt))      # tolto a mano: il branch resta senza worktree
    common = Path(g(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    old = time.time() - 30 * DAY
    os.utime(common / "logs" / "refs" / "heads" / "brief" / "P1-x", (old, old))
    out = script(repo).stdout
    assert "BRANCH   brief/P1-x — 1 commit non su main" in out and "B350" in out
    script(repo, "--clean")
    assert has_branch(repo, "brief/P1-x")


def test_parked_work_reverted_in_a_worktree_is_flagged_not_removed(repo):
    wt = add_worktree(repo, "p2", "brief/P2-x")
    commit(wt, name="feature.py", msg="feature")
    g(wt, "revert", "--no-edit", "HEAD")
    age(repo, wt, "brief/P2-x", 30 * DAY)
    assert "FERMO" in script(repo).stdout
    script(repo, "--clean")
    assert wt.exists()


def test_commit_dropped_by_reset_survives_on_a_stray_branch(repo):
    wt = add_worktree(repo, "p3", "brief/P3-x")
    commit(wt, name="wip.txt", msg="wip")
    g(wt, "reset", "-q", "--hard", "origin/main")
    g(repo, "worktree", "remove", str(wt))
    common = Path(g(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    old = time.time() - 30 * DAY
    os.utime(common / "logs" / "refs" / "heads" / "brief" / "P3-x", (old, old))
    script(repo, "--clean")
    assert has_branch(repo, "brief/P3-x")


@needs_lsof
def test_amended_commit_does_not_block_a_merged_worktree(repo):
    """Il commit prima dell'amend è stato sostituito di proposito: non è lavoro perso."""
    wt = add_worktree(repo, "p4", "brief/P4-x")
    (wt / "app.txt").write_text("prima versione\n")
    g(wt, "commit", "-q", "-a", "-m", "v1")
    (wt / "app.txt").write_text("versione corretta\n")
    g(wt, "commit", "-q", "-a", "--amend", "-m", "v1 corretta")
    push_to_main(wt)
    age(repo, wt, "brief/P4-x", 3 * HOUR)
    script(repo, "--clean")
    assert not wt.exists()


@needs_lsof
def test_rebased_away_commits_do_not_block_a_merged_worktree(repo):
    wt = add_worktree(repo, "p5", "brief/P5-x")
    (wt / "app.txt").write_text("branch\n")
    g(wt, "commit", "-q", "-a", "-m", "branch side")
    (repo / "app.txt").write_text("main\n")
    g(repo, "commit", "-q", "-a", "-m", "main side")
    g(repo, "push", "-q", "origin", "main")
    g(wt, "fetch", "-q", "origin")
    subprocess.run(["git", "rebase", "origin/main"], cwd=wt, capture_output=True)
    (wt / "app.txt").write_text("main + branch\n")
    g(wt, "add", "app.txt")
    subprocess.run(["git", "-c", "core.editor=true", "rebase", "--continue"], cwd=wt, capture_output=True, check=True)
    push_to_main(wt)
    age(repo, wt, "brief/P5-x", 3 * HOUR)
    script(repo, "--clean")
    assert not wt.exists()


def test_missing_worktree_says_whether_prune_would_lose_commits(repo):
    safe = add_worktree(repo, "m1", "brief/M1-x")
    risky = add_worktree(repo, "m2")
    commit(risky, name="detached.txt")
    g(risky, "checkout", "-q", "--detach", "origin/main")
    shutil.rmtree(safe)
    shutil.rmtree(risky)
    out = script(repo).stdout
    safe_line = next(ln for ln in out.splitlines() if "proj-m1" in ln)
    risky_line = next(ln for ln in out.splitlines() if "proj-m2" in ln)
    assert "nessun commit perso" in safe_line
    assert "recuperali prima di `git worktree prune`" in risky_line


@needs_lsof
def test_fetch_prune_in_config_does_not_drop_unmerged_remote_refs(repo):
    origin = repo.parent / "origin.git"
    side = add_worktree(repo, "side", "brief/F1-wip")
    commit(side, name="wip.txt")
    g(side, "push", "-q", "origin", "HEAD:brief/F1-wip")
    g(repo, "worktree", "remove", "--force", str(side))
    g(repo, "branch", "-D", "brief/F1-wip")
    g(repo, "fetch", "-q", "origin")
    g(origin, "branch", "-D", "brief/F1-wip")
    g(repo, "config", "fetch.prune", "true")
    script(repo, "--clean")
    assert "refs/remotes/origin/brief/F1-wip" in g(repo, "for-each-ref", "--format=%(refname)", "refs/remotes")


def test_start_brief_never_suggests_a_raw_worktree_remove():
    text = (REPO_ROOT / "scripts" / "start_brief.py").read_text()
    assert "Rimuovilo con: git worktree remove" not in text


def test_reverted_work_that_arrived_by_fast_forward_is_not_deleted(repo):
    """Il commit annullato non è in nessun reflog del branch: lo trova solo la storia intera."""
    tmp = add_worktree(repo, "tmp", "scratch/T1")
    commit(tmp, name="feature.py", msg="feature")
    g(tmp, "revert", "--no-edit", "HEAD")
    g(repo, "worktree", "remove", str(tmp))
    g(repo, "branch", "brief/Q1-x", "scratch/T1")   # reflog di brief/Q1-x: solo la punta
    g(repo, "branch", "-D", "scratch/T1")
    common = Path(g(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    old = time.time() - 30 * DAY
    os.utime(common / "logs" / "refs" / "heads" / "brief" / "Q1-x", (old, old))
    assert "BRANCH   brief/Q1-x — 1 commit non su main" in script(repo).stdout
    script(repo, "--clean")
    assert has_branch(repo, "brief/Q1-x")


def test_orphan_worktree_without_commits_is_read_not_an_error(repo):
    wt = repo.parent / "proj-orphan"
    g(repo, "worktree", "add", "-q", "--orphan", "-b", "brief/O1-x", str(wt))
    (wt / "draft.txt").write_text("bozza")
    out = script(repo).stdout
    line = next(ln for ln in out.splitlines() if "proj-orphan" in ln)
    assert "IN CORSO" in line and "1 file non committato" in line


def test_aborted_rebase_is_not_a_rewrite(repo):
    """Un rebase interrotto lascia «rebase (start)» nel reflog ma non sostituisce niente."""
    wt = add_worktree(repo, "p6", "brief/P6-x")
    (wt / "app.txt").write_text("branch\n")
    g(wt, "commit", "-q", "-a", "-m", "lavoro")
    work = g(wt, "rev-parse", "HEAD")
    (repo / "app.txt").write_text("main\n")
    g(repo, "commit", "-q", "-a", "-m", "main side")
    g(repo, "push", "-q", "origin", "main")
    g(wt, "fetch", "-q", "origin")
    subprocess.run(["git", "rebase", "origin/main"], cwd=wt, capture_output=True)
    g(wt, "rebase", "--abort")
    g(wt, "reset", "-q", "--hard", "origin/main")
    age(repo, wt, "brief/P6-x", 30 * DAY)
    out = script(repo).stdout
    assert "FERMO" in out and work[:7] in out
    script(repo, "--clean")
    assert wt.exists()


@needs_lsof
def test_rebase_with_several_commits_rewrites_the_whole_series(repo):
    wt = add_worktree(repo, "p7", "brief/P7-x")
    (wt / "app.txt").write_text("branch 1\n")
    g(wt, "commit", "-q", "-a", "-m", "uno")
    (wt / "app.txt").write_text("branch 2\n")
    g(wt, "commit", "-q", "-a", "-m", "due")
    (repo / "app.txt").write_text("main\n")
    g(repo, "commit", "-q", "-a", "-m", "main side")
    g(repo, "push", "-q", "origin", "main")
    g(wt, "fetch", "-q", "origin")
    for _ in range(2):
        subprocess.run(["git", "rebase", "origin/main"], cwd=wt, capture_output=True)
        (wt / "app.txt").write_text("risolto\n")
        g(wt, "add", "app.txt")
        subprocess.run(["git", "-c", "core.editor=true", "rebase", "--continue"], cwd=wt, capture_output=True)
        if not (Path(g(wt, "rev-parse", "--absolute-git-dir")) / "rebase-merge").exists():
            break
    push_to_main(wt)
    age(repo, wt, "brief/P7-x", 3 * HOUR)
    script(repo, "--clean")
    assert not wt.exists()


# ── revisione avversariale, terzo giro ──────────────────────────────────────


def moved_main(repo, line="main\n"):
    (repo / "app.txt").write_text(line)
    g(repo, "commit", "-q", "-a", "-m", "main va avanti")
    g(repo, "push", "-q", "origin", "main")


@pytest.mark.parametrize("interactive", [False, True])
def test_finished_rebase_then_reset_keeps_the_work(repo, interactive):
    """Il risultato del rebase non è «riscritto»: dopo un reset --hard è l'unica copia del lavoro."""
    wt = add_worktree(repo, "s1", "brief/S1-x")
    commit(wt, name="work.txt", msg="lavoro")
    commit(repo, name="other.txt", msg="main va avanti")
    g(repo, "push", "-q", "origin", "main")
    g(wt, "fetch", "-q", "origin")
    if interactive:
        subprocess.run(["git", "rebase", "-i", "origin/main"], cwd=wt, capture_output=True, check=True,
                       env={**os.environ, "GIT_SEQUENCE_EDITOR": "true"})
    else:
        g(wt, "rebase", "-q", "origin/main")
    g(wt, "reset", "-q", "--hard", "origin/main")
    age(repo, wt, "brief/S1-x", 30 * DAY)
    assert "FERMO" in script(repo).stdout
    script(repo, "--clean")
    assert wt.exists() and has_branch(repo, "brief/S1-x")


def test_amend_rewrites_only_the_amended_commit_not_its_ancestors(repo):
    wt = add_worktree(repo, "s2", "brief/S2-x")
    commit(wt, name="feature.py", msg="feature")
    g(wt, "revert", "--no-edit", "HEAD")
    g(wt, "commit", "-q", "--amend", "-m", "parcheggio la feature")
    g(wt, "reset", "-q", "--hard", "origin/main")
    age(repo, wt, "brief/S2-x", 30 * DAY)
    script(repo, "--clean")
    assert wt.exists() and has_branch(repo, "brief/S2-x")


@needs_lsof
@pytest.mark.parametrize("pull_args", [["pull", "-q", "--rebase"], ["-c", "pull.rebase=true", "pull", "-q"]])
def test_pull_rebase_counts_as_a_rewrite(repo, pull_args):
    wt = add_worktree(repo, "s3", "brief/S3-x")
    (wt / "app.txt").write_text("brief\n")
    g(wt, "commit", "-q", "-a", "-m", "brief")
    commit(repo, name="other.txt", msg="main va avanti")
    g(repo, "push", "-q", "origin", "main")
    g(wt, *pull_args)
    push_to_main(wt)
    g(repo, "pull", "-q", "--ff-only")
    moved_main(repo, "main riscrive la riga\n")   # il commit prima del rebase non si unisce più pulito
    g(wt, "fetch", "-q", "origin")
    age(repo, wt, "brief/S3-x", 3 * HOUR)
    script(repo, "--clean")
    assert not wt.exists()


@needs_lsof
def test_series_cherry_picked_on_main_with_a_later_revision_is_merged(repo):
    """c2 rivede la riga di c1; main ha le copie di entrambi: c1 non è lavoro perso."""
    wt = add_worktree(repo, "s4", "brief/S4-x")
    (wt / "app.txt").write_text("prima\n")
    g(wt, "commit", "-q", "-a", "-m", "c1")
    (wt / "app.txt").write_text("rivista\n")
    g(wt, "commit", "-q", "-a", "-m", "c2")
    commit(repo, name="other.txt", msg="main va avanti")
    g(repo, "cherry-pick", "brief/S4-x~1", "brief/S4-x")
    g(repo, "push", "-q", "origin", "main")
    g(repo, "fetch", "-q", "origin")
    age(repo, wt, "brief/S4-x", 3 * HOUR)
    script(repo, "--clean")
    assert not wt.exists()


def test_remote_preview_branch_amended_and_force_pushed_is_on_main(repo):
    wt = add_worktree(repo, "s5", "brief/S5-x")
    (wt / "app.txt").write_text("anteprima\n")
    g(wt, "commit", "-q", "-a", "-m", "v1")
    g(wt, "push", "-q", "origin", "HEAD:brief/S5-x")
    (wt / "app.txt").write_text("v1 corretta\n")
    g(wt, "commit", "-q", "-a", "--amend", "-m", "v1 corretta")
    g(wt, "push", "-q", "-f", "origin", "HEAD:brief/S5-x")
    push_to_main(wt)
    line = next(ln for ln in script(repo).stdout.splitlines() if "REMOTO" in ln)
    assert "già su main" in line, line


def test_pushing_main_marks_the_pushed_commit_as_on_main(repo):
    wt = add_worktree(repo, "s6", "brief/S6-x")
    commit(wt)
    sha = g(wt, "rev-parse", "HEAD")
    before = next(ln for ln in script(repo).stdout.splitlines() if "proj-s6" in ln)
    assert "commit non su main" in before
    after = next(ln for ln in script(repo, "--pushing-main", sha).stdout.splitlines() if "proj-s6" in ln)
    assert "commit non su main" not in after and "SU MAIN" in after
    assert script(repo, "--clean", "--pushing-main", sha, check=False).returncode == 2


def test_pre_push_hook_passes_the_main_push_to_the_report():
    hook = (REPO_ROOT / ".githooks" / "pre-push").read_text()
    assert "refs/heads/main" in hook and "--pushing-main" in hook
