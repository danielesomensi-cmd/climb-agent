import os
import sys
from pathlib import Path

import pytest

# B165d: disable rate limiting during tests
os.environ.setdefault("RATE_LIMIT_ENABLED", "0")

# Ensure repo root is importable so `import backend...` works in pytest
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def isolate_storage_write_dirs(tmp_path, monkeypatch):
    """B-TEST-COACH-ISOLATION: never let a test write into backend/data/.

    Individual test modules isolate ``STATE_PATH``, but nothing isolated the
    OTHER write sinks in ``storage_file`` — the log dir, the per-user dir, the
    week archive and the recovery-code file. So every run appended to the real
    ``backend/data/logs/coach_messages.jsonl`` and created directories under
    ``backend/data/users/``. Both are gitignored, which is what made the damage
    invisible to ``git status``.

    The concrete failure: coach messages accumulate across runs, and once the
    same UTC day reaches ``DAILY_MESSAGE_LIMIT`` (30, ``coach/service.py``) the
    endpoint answers 429 and three tests in ``test_a243_adhoc_builder.py`` fail
    on completely unchanged code — then pass again after UTC midnight. A test
    suite whose result depends on how many times it has been run today is worse
    than a failing one, because it teaches you to distrust real failures.

    B291 — ``STATE_PATH`` IS now redirected here too. B-TEST-COACH-ISOLATION
    left it alone on the grounds that "modules that need it already point it at
    their own tmp copy and a global override would fight those". The first half
    was only true of ~15 of the ~31 modules that touch it; the second half turns
    out not to happen at all.

    Why it does not fight: ``monkeypatch`` is function-scoped, so this fixture
    and any module-level fixture share ONE monkeypatch object. This autouse
    fixture runs first, a module fixture patches the same attribute afterwards
    and therefore wins for that test, and teardown undoes both in reverse order.
    A global redirect is a *default*, not an override.

    Why it was needed: ``storage_file._user_state_path(user_id)`` falls back to
    ``STATE_PATH`` whenever ``user_id`` is falsy, and under pytest
    ``_auth_enforced()`` is False, so every request without an ``X-User-ID``
    header wrote into the real ``backend/data/user_state.json``. Unlike the
    gitignored sinks above, that file IS tracked — so each run left the repo
    dirty, which both masks real changes and invites committing test state.

    The tmp file is seeded with a copy of the real one so any test that relies
    on its contents behaves exactly as before; only the writes are redirected.

    Everything patched below is resolved as a module attribute at call time (or
    is a module-level constant), so reassigning it is enough — no other module
    imports these names directly.
    """
    import shutil

    from backend.api import deps
    from backend.engine import storage_file

    data_dir = tmp_path / "data"
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(storage_file, "DATA_DIR", data_dir, raising=False)
    monkeypatch.setattr(storage_file, "USERS_DIR", data_dir / "users", raising=False)
    # `_CODES_PATH` was redirected here too, until B320 retired the
    # recovery-code feature and with it the only writer of that file.

    tmp_state = data_dir / "user_state.json"
    real_state = REPO_ROOT / "backend" / "data" / "user_state.json"
    if real_state.exists():
        shutil.copy2(real_state, tmp_state)
    monkeypatch.setattr(storage_file, "STATE_PATH", tmp_state, raising=False)
    # deps re-exports a copy at import time; nothing in production reads it, but
    # keep the two aligned so a test patching one does not see the other stale.
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state, raising=False)
    yield


# ---------------------------------------------------------------------------
# B388 — no test may straddle a midnight.
#
# There is no injectable clock in the backend: ~60 modules read
# ``date.today()`` / ``datetime.now()`` directly, per call. Many tests read
# "today" in a fixture (e.g. the current Monday, to seed a week plan) and then
# hit an endpoint that reads it again — and the two reads only agree while the
# wall clock stays on the same day. Run the suite across Sunday->Monday local
# midnight and a test whose fixture ran at 23:59:59.5 sees the server answer at
# 00:00:00 for the *next* week: ``assert '2026-10-12' == '2026-10-19'``, 422 on
# a "past" week, guard checks on the wrong day (55 tests reproduced it). The
# product is right — a request after midnight does belong to the new week; the
# tests are wrong to assume the day cannot change under them.
#
# Freezing the clock for the whole suite would mean patching ``datetime`` in
# every module (no freezegun in the venv, and ``date.today`` cannot be
# monkeypatched on the C type). Instead: a test never STARTS within
# ``_MIDNIGHT_GUARD_S`` seconds of a local or UTC midnight — it waits the
# boundary out first. No test in the suite runs anywhere near that long, so no
# test can see two dates; the cost is at most one short wait per run that
# happens to cross midnight. Day boundaries are guarded, not only Mondays,
# because day-based logic (trial days, "past session", per-day guards) has the
# same shape; UTC too, because the coach daily limit counts UTC days.
# ---------------------------------------------------------------------------
_MIDNIGHT_GUARD_S = 10.0


def _seconds_until_next_midnight(now_ts: float) -> float:
    """Seconds from ``now_ts`` to the nearest upcoming local or UTC midnight."""
    from datetime import datetime, time, timedelta, timezone

    local = datetime.fromtimestamp(now_ts)
    next_local = datetime.combine(local.date() + timedelta(days=1), time())
    utc = datetime.fromtimestamp(now_ts, timezone.utc)
    next_utc = datetime.combine(utc.date() + timedelta(days=1), time(), timezone.utc)
    return min(next_local.timestamp(), next_utc.timestamp()) - now_ts


def _midnight_wait_s(now_ts: float, guard_s: float = _MIDNIGHT_GUARD_S) -> float:
    """How long a test starting at ``now_ts`` must wait so it cannot straddle a
    midnight: 0 when the next midnight is more than ``guard_s`` away, else the
    time to just past it."""
    left = _seconds_until_next_midnight(now_ts)
    return left + 0.05 if left <= guard_s else 0.0


def _wait_out_midnight(now, sleep) -> float:
    """Sleep past an imminent midnight; returns the seconds waited."""
    wait = _midnight_wait_s(now())
    if wait > 0:
        sleep(wait)
    return wait


@pytest.fixture(autouse=True)
def _no_test_straddles_midnight():
    import time

    _wait_out_midnight(time.time, time.sleep)
    yield
