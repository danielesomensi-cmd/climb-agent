"""B291 — no test may write into the repo's real ``backend/data/``.

History: B-TEST-COACH-ISOLATION isolated the log dir, the per-user dir and the
recovery-code file, but deliberately left ``STATE_PATH`` alone. That gap was
real: ``storage_file._user_state_path()`` falls back to ``STATE_PATH`` whenever
``user_id`` is falsy, and under pytest ``_auth_enforced()`` is False, so every
API call without an ``X-User-ID`` header wrote into the tracked
``backend/data/user_state.json``. Every run left the repo dirty — which masks
real changes and invites committing test state.

These tests fail if any of those redirects is ever dropped.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.engine import storage_file

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_DATA_DIR = REPO_ROOT / "backend" / "data"
REAL_STATE = REAL_DATA_DIR / "user_state.json"


def _is_isolated(path) -> bool:
    """True when *path* is NOT inside the repo's real data directory."""
    try:
        Path(path).resolve().relative_to(REAL_DATA_DIR.resolve())
        return False
    except ValueError:
        return True


class TestWriteSinksAreRedirected:
    """Each of these is a sink a test could write through."""

    def test_state_path_is_isolated(self):
        assert _is_isolated(storage_file.STATE_PATH), (
            f"STATE_PATH points at the real repo file: {storage_file.STATE_PATH}"
        )

    def test_deps_state_path_matches_storage(self):
        """The two must not drift — a test patching one would miss the other."""
        assert Path(deps.STATE_PATH) == Path(storage_file.STATE_PATH)

    def test_data_dir_is_isolated(self):
        assert _is_isolated(storage_file.DATA_DIR)

    def test_users_dir_is_isolated(self):
        assert _is_isolated(storage_file.USERS_DIR)

    def test_recovery_codes_path_is_isolated(self):
        assert _is_isolated(storage_file._CODES_PATH)


class TestAnonymousWritesStayOutOfTheRepo:
    """The exact path that caused the leak: a request with no user id."""

    def test_anonymous_state_write_does_not_touch_the_real_file(self):
        before = REAL_STATE.read_bytes() if REAL_STATE.exists() else None

        with TestClient(app) as client:
            # No X-User-ID header → user_id is None → _user_state_path falls
            # back to STATE_PATH. This is what used to hit the repo.
            r = client.put("/api/state", json={"goal": {"target_grade": "9a"}})
            assert r.status_code in (200, 401, 402), r.status_code

        after = REAL_STATE.read_bytes() if REAL_STATE.exists() else None
        assert after == before, "an anonymous write reached backend/data/user_state.json"

    def test_the_write_actually_landed_somewhere(self):
        """Guard against the test passing because nothing was written at all."""
        with TestClient(app) as client:
            client.put("/api/state", json={"goal": {"target_grade": "9a"}})
            got = client.get("/api/state")

        if got.status_code == 200:
            assert got.json().get("goal", {}).get("target_grade") == "9a"


class TestFixtureOverrideStillWins:
    """A module-level fixture must still be able to point STATE_PATH elsewhere.

    This is the objection B-TEST-COACH-ISOLATION raised against a global
    redirect ("it would fight the modules that isolate it themselves"). It does
    not: monkeypatch is function-scoped, the autouse fixture runs first, and a
    later patch simply wins.
    """

    @pytest.fixture(autouse=True)
    def _own_state(self, tmp_path, monkeypatch):
        self.mine = tmp_path / "my_own_state.json"
        monkeypatch.setattr(storage_file, "STATE_PATH", self.mine, raising=False)
        yield

    def test_module_fixture_overrides_the_global_default(self):
        assert Path(storage_file.STATE_PATH) == self.mine
        assert _is_isolated(storage_file.STATE_PATH)
