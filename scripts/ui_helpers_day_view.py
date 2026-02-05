from __future__ import annotations

import inspect
import json
import tempfile
from datetime import date as _date
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
EXERCISES_PATH = REPO_ROOT / "catalog" / "exercises" / "v1" / "exercises.json"
SESSIONS_DIR = REPO_ROOT / "catalog" / "sessions" / "v1"
USER_STATE_PATH = REPO_ROOT / "data" / "user_state.json"

DIFFICULTIES = ("too_easy", "easy", "ok", "hard", "too_hard", "fail")
OVERRIDE_MODES = ("none", "absolute_load_kg", "delta_kg", "multiplier")


# ----------------------------
# Small IO helpers
# ----------------------------
def _load_json_path(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json_path(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def parse_date_input(date_str: str) -> _date:
    try:
        return _date.fromisoformat(date_str)
    except Exception as exc:
        raise ValueError("Invalid date. Use YYYY-MM-DD.") from exc


def list_session_paths() -> List[Path]:
    if not SESSIONS_DIR.exists():
        return []
    return sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stem)


def session_dropdown_choices() -> List[Tuple[str, str]]:
    return [(p.stem, str(p)) for p in list_session_paths()]


def read_user_state() -> Dict[str, Any]:
    if not USER_STATE_PATH.exists():
        raise FileNotFoundError(f"user_state.json not found at {USER_STATE_PATH}")
    return _load_json_path(USER_STATE_PATH)


def write_user_state(user_state: Dict[str, Any]) -> str:
    _dump_json_path(USER_STATE_PATH, user_state)
    return str(USER_STATE_PATH)


# ----------------------------
# Resolver compat wrapper
# ----------------------------
def _resolve_session_compat(*, session_path: str, out_path: str, user_state_override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calls catalog.engine.resolve_session.resolve_session but adapts to signature differences.
    We always provide repo_root, session_path, templates_dir, exercises_path, out_path when supported.
    """
    from catalog.engine import resolve_session as mod  # local import
    fn = getattr(mod, "resolve_session")
    sig = inspect.signature(fn)
    params = sig.parameters

    kwargs: Dict[str, Any] = {}

    # Required-ish roots
    if "repo_root" in params:
        kwargs["repo_root"] = str(REPO_ROOT)
    elif "root" in params:
        kwargs["root"] = str(REPO_ROOT)

    # Session path
    if "session_path" in params:
        kwargs["session_path"] = session_path
    elif "session_file" in params:
        kwargs["session_file"] = session_path
    elif "session_json_path" in params:
        kwargs["session_json_path"] = session_path
    else:
        # fallback: some resolvers accept session_id; but we need a path-based call for now
        kwargs["session_path"] = session_path

    # Catalog paths
    if "templates_dir" in params:
        kwargs["templates_dir"] = "catalog/templates"
    if "exercises_path" in params:
        kwargs["exercises_path"] = "catalog/exercises/v1/exercises.json"

    # Output
    if "out_path" in params:
        kwargs["out_path"] = out_path
    elif "output_path" in params:
        kwargs["output_path"] = out_path

    # Optional knobs
    if "user_state_override" in params:
        kwargs["user_state_override"] = user_state_override
    if "write_output" in params:
        kwargs["write_output"] = False

    return fn(**kwargs)


def resolve_session_with_context(
    *,
    session_path: str,
    target_date: str,
    location: str,
    user_state: Dict[str, Any],
) -> Dict[str, Any]:
    session = _load_json_path(Path(session_path))
    context = dict(session.get("context") or {})
    context["target_date"] = target_date
    context["date"] = target_date
    context["location"] = location
    session["context"] = context

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        tmp_session = tmp / "session.json"
        tmp_resolved = tmp / "resolved.json"
        _dump_json_path(tmp_session, session)
        return _resolve_session_compat(
            session_path=str(tmp_session),
            out_path=str(tmp_resolved),
            user_state_override=user_state,
        )


# ----------------------------
# Plan table extraction (flexible)
# ----------------------------
def _format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _first_present(mapping: Dict[str, Any], keys: Iterable[str]) -> Any:
    for k in keys:
        if k in mapping:
            return mapping.get(k)
    return None


def build_plan_table(session_instance: Dict[str, Any]) -> List[Dict[str, str]]:
    # most common structure: {"resolved_session": {"exercise_instances": [...]}}
    rs = session_instance.get("resolved_session") or session_instance.get("session") or session_instance
    instances = (rs.get("exercise_instances") if isinstance(rs, dict) else None) or []
    rows: List[Dict[str, str]] = []
    for inst in instances:
        pres = inst.get("prescription") or {}
        rest_value = _first_present(pres, ("rest_seconds", "rest", "rest_sec", "rest_minutes"))
        rows.append(
            {
                "exercise_id": _format_cell(inst.get("exercise_id")),
                "sets": _format_cell(pres.get("sets")),
                "reps": _format_cell(pres.get("reps")),
                "load_kg": _format_cell(pres.get("load_kg")),
                "rest": _format_cell(rest_value),
                "notes": _format_cell(inst.get("notes") or pres.get("notes")),
            }
        )
    return rows


def extract_exercise_ids(table: List[Dict[str, str]]) -> List[str]:
    return [r["exercise_id"] for r in table if r.get("exercise_id")]


def load_exercises_by_id() -> Dict[str, Dict[str, Any]]:
    raw = _load_json_path(EXERCISES_PATH)
    exercises = raw if isinstance(raw, list) else raw.get("exercises") or []
    out: Dict[str, Dict[str, Any]] = {}
    for ex in exercises:
        ex_id = ex.get("id")
        if ex_id:
            out[str(ex_id)] = ex
    return out


# ----------------------------
# Overrides + adjustments (use existing closed_loop if present)
# ----------------------------
def get_adjustment_state(user_state: Dict[str, Any], exercise_id: str) -> Dict[str, Any]:
    adj = user_state.get("adjustments") or {}
    per = (adj.get("per_exercise") or {})
    st = per.get(exercise_id) or {}
    return {
        "multiplier": float(st.get("multiplier", 1.0)),
        "streak": int(st.get("streak", 0)),
        "last_update": st.get("last_update"),
    }


def apply_override(
    user_state: Dict[str, Any],
    exercise_id: str,
    mode: str,
    value: Optional[str],
    expires: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not exercise_id:
        return None
    if mode not in OVERRIDE_MODES or mode == "none":
        return None
    if value is None or str(value).strip() == "":
        return None

    try:
        value_num = float(value)
    except ValueError as exc:
        raise ValueError("Override value must be a number.") from exc

    expires_count = 1
    if expires is not None and str(expires).strip() != "":
        try:
            expires_count = int(float(expires))
        except ValueError as exc:
            raise ValueError("Override expires must be a number.") from exc

    overrides = user_state.setdefault("overrides", {})
    per_ex = overrides.setdefault("per_exercise", {})
    override = {
        "mode": mode,
        "value": value_num,
        "expires": {"type": "occurrences", "n": max(expires_count, 1)},
    }
    per_ex[exercise_id] = override
    return override


def update_adjustments_deterministic(
    *,
    user_state: Dict[str, Any],
    exercise_id: str,
    difficulty: str,
    feedback_date: str,
    exercises_by_id: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    if difficulty not in DIFFICULTIES:
        raise ValueError("Unsupported difficulty.")

    # Prefer canonical closed_loop logic if available
    try:
        from catalog.engine.adaptation.closed_loop import (
            DEFAULT_CONFIG,
            EASY_DIFFICULTIES,
            HARD_DIFFICULTIES,
            compute_next_multiplier,
        )
        from catalog.engine.cluster_utils import cluster_key_for_exercise
    except Exception:  # pragma: no cover
        DEFAULT_CONFIG = {}
        EASY_DIFFICULTIES = {"too_easy", "easy"}
        HARD_DIFFICULTIES = {"hard", "too_hard", "fail"}

        def compute_next_multiplier(mult: float, diff: str, streak: int, cfg: Dict[str, Any]) -> float:
            # minimal fallback: nudge
            if diff in {"too_easy"}:
                return mult * 1.05
            if diff in {"easy"}:
                return mult * 1.02
            if diff in {"hard"}:
                return mult * 0.98
            if diff in {"too_hard", "fail"}:
                return mult * 0.95
            return mult

        def cluster_key_for_exercise(ex: Dict[str, Any]) -> str:
            return ex.get("cluster_key") or ex.get("pattern") or "unknown"

    adj = user_state.setdefault("adjustments", {})
    per = adj.setdefault("per_exercise", {})
    cur = per.get(exercise_id, {})
    mult = float(cur.get("multiplier", 1.0))
    streak = int(cur.get("streak", 0))

    cfg = adj.get("config") or DEFAULT_CONFIG
    next_mult = float(compute_next_multiplier(mult, difficulty, streak, cfg))

    if difficulty in HARD_DIFFICULTIES:
        next_streak = streak + 1
    elif difficulty in EASY_DIFFICULTIES:
        next_streak = 0
    else:
        next_streak = streak

    d = parse_date_input(feedback_date)
    per[exercise_id] = {"multiplier": next_mult, "streak": next_streak, "last_update": f"{d.isoformat()}T00:00:00"}

    # cooldown heuristic (keep simple)
    cooldown_days = 2 if difficulty in {"fail", "too_hard"} else (1 if difficulty == "hard" else 0)
    if cooldown_days:
        ex = exercises_by_id.get(exercise_id)
        if ex:
            until = d + timedelta(days=cooldown_days)
            cds = user_state.setdefault("cooldowns", {})
            per_cluster = cds.setdefault("per_cluster", {})
            ck = cluster_key_for_exercise(ex)
            per_cluster[ck] = {"until_date": until.isoformat(), "reason": f"difficulty:{difficulty}", "last_updated": d.isoformat()}

    return user_state


def summarize_delta(
    *,
    today_table: List[Dict[str, str]],
    tomorrow_table: List[Dict[str, str]],
    multiplier_before: float,
    multiplier_after: float,
) -> str:
    today_ids = [r.get("exercise_id", "") for r in today_table]
    tomorrow_ids = [r.get("exercise_id", "") for r in tomorrow_table]
    lines: List[str] = []

    if today_ids != tomorrow_ids:
        lines.append("- exercise lineup changed")
        lines.append(f"  - today: {', '.join(filter(None, today_ids)) or 'n/a'}")
        lines.append(f"  - tomorrow: {', '.join(filter(None, tomorrow_ids)) or 'n/a'}")
    else:
        lines.append("- exercise lineup unchanged")

    load_changes: List[str] = []
    for a, b in zip(today_table, tomorrow_table):
        if a.get("exercise_id") == b.get("exercise_id") and a.get("load_kg") != b.get("load_kg"):
            load_changes.append(f"{a.get('exercise_id')}: {a.get('load_kg')} → {b.get('load_kg')}")

    if load_changes:
        lines.append("- load changes")
        for c in load_changes:
            lines.append(f"  - {c}")
    else:
        lines.append("- load changes: none")

    if float(multiplier_before) != float(multiplier_after):
        lines.append(f"- multiplier: {multiplier_before:.3f} → {multiplier_after:.3f}")
    else:
        lines.append(f"- multiplier: {multiplier_before:.3f} (unchanged)")

    return "\n".join(lines)


def override_summary(override: Optional[Dict[str, Any]]) -> str:
    if not override:
        return "none"
    exp = override.get("expires") or {}
    return f"mode={override.get('mode')} value={override.get('value')} expires={exp.get('type')}:{exp.get('n')}"
