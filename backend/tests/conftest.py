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
    monkeypatch.setattr(
        storage_file, "_CODES_PATH", data_dir / "recovery_codes.json", raising=False
    )

    tmp_state = data_dir / "user_state.json"
    real_state = REPO_ROOT / "backend" / "data" / "user_state.json"
    if real_state.exists():
        shutil.copy2(real_state, tmp_state)
    monkeypatch.setattr(storage_file, "STATE_PATH", tmp_state, raising=False)
    # deps re-exports a copy at import time; nothing in production reads it, but
    # keep the two aligned so a test patching one does not see the other stale.
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state, raising=False)
    yield
