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

    ``STATE_PATH`` is deliberately NOT redirected here: modules that need it
    already point it at their own tmp copy of the fixture state, and a global
    override would fight those. Everything patched below is resolved as a module
    attribute at call time (or is a module-level constant), so reassigning it is
    enough — no other module imports these names directly.
    """
    from backend.engine import storage_file

    data_dir = tmp_path / "data"
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(storage_file, "DATA_DIR", data_dir, raising=False)
    monkeypatch.setattr(storage_file, "USERS_DIR", data_dir / "users", raising=False)
    monkeypatch.setattr(
        storage_file, "_CODES_PATH", data_dir / "recovery_codes.json", raising=False
    )
    yield
