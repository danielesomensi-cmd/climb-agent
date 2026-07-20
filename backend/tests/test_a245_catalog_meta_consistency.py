"""A245 E-6 (B19) — catalog/_SESSION_META consistency, moved out of import time.

`planner_v2` used to run `_validate_session_meta_equipment()` at module import:
~35 JSON files opened on every import of a hot engine module (every worker boot,
every test collection), wrapped in `except Exception: pass`, reporting drift as
a log warning nobody reads.

Same check, same function, run here — where a mismatch fails the build.
"""

import json
import os

from backend.engine.planner_v2 import _SESSION_META, _validate_session_meta_equipment

SESSIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "catalog", "sessions", "v1",
)


def test_session_meta_required_equipment_matches_the_catalog():
    """The check that used to be an ignorable warning is now an assertion."""
    mismatches = []
    for sid, meta in _SESSION_META.items():
        path = os.path.join(SESSIONS_DIR, f"{sid}.json")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        json_eq = set(data.get("required_equipment") or [])
        meta_eq = set(meta.get("required_equipment") or [])
        if json_eq != meta_eq:
            mismatches.append(
                f"{sid}: meta={sorted(meta_eq)} json={sorted(json_eq)}"
            )
    assert not mismatches, "required_equipment drift between _SESSION_META and catalog:\n" + "\n".join(mismatches)


def test_validation_helper_still_runs_clean():
    """The original function is kept and callable — it just isn't run at import."""
    _validate_session_meta_equipment()


def test_planner_v2_import_does_no_catalog_io(monkeypatch):
    """Regression guard for B19: re-importing must not touch the filesystem."""
    import importlib
    import builtins

    opened = []
    real_open = builtins.open

    def tracking_open(path, *a, **kw):
        opened.append(str(path))
        return real_open(path, *a, **kw)

    monkeypatch.setattr(builtins, "open", tracking_open)

    import backend.engine.planner_v2 as pv2
    importlib.reload(pv2)

    catalog_reads = [p for p in opened if "catalog" in p and p.endswith(".json")]
    assert not catalog_reads, f"planner_v2 import read catalog files: {catalog_reads[:5]}"
