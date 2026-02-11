from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from catalog.engine.closed_loop_v1 import append_jsonl, apply_day_result_to_user_state, build_log_entry, ensure_planning_defaults
from catalog.engine.progression_v1 import apply_feedback, canonical_feedback_label, inject_targets
from catalog.engine.resolve_session import resolve_session


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _find_day(plan: Dict[str, Any], date_value: str) -> Dict[str, Any]:
    for week in plan.get("weeks") or []:
        for day in week.get("days") or []:
            if day.get("date") == date_value:
                return day
    raise ValueError(f"No day found for date={date_value}")


def _session_file(session_id: str) -> Path:
    return Path("catalog/sessions/v1") / f"{session_id}.json"


def _validate_planned_session(session_entry: Dict[str, Any]) -> None:
    if session_entry.get("location") == "gym" and not session_entry.get("gym_id"):
        sid = session_entry.get("session_id")
        raise ValueError(f"Planned gym session must include non-null gym_id: session_id={sid}")


def _resolve_single(*, repo_root: Path, session_entry: Dict[str, Any], date_value: str, user_state: Dict[str, Any]) -> Dict[str, Any]:
    _validate_planned_session(session_entry)
    sid = str(session_entry["session_id"])
    source = repo_root / _session_file(sid)
    if not source.exists():
        raise FileNotFoundError(f"Session file missing for session_id={sid}: {source}")

    payload = _read_json(source)
    context = payload.setdefault("context", {})
    context["location"] = session_entry.get("location")
    context["gym_id"] = session_entry.get("gym_id")
    context["target_date"] = date_value

    tmp_dir = repo_root / "out"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".json", dir=tmp_dir, delete=False, encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
        temp_name = Path(fh.name).relative_to(repo_root)

    try:
        resolved = resolve_session(
            repo_root=str(repo_root),
            session_path=str(temp_name),
            templates_dir="catalog/templates",
            exercises_path="catalog/exercises/v1/exercises.json",
            out_path="out/tmp/ignore.json",
            user_state_override=user_state,
            write_output=False,
        )
    finally:
        (repo_root / temp_name).unlink(missing_ok=True)

    selected_modules = [m.get("template_id") for m in (resolved.get("resolved_session") or {}).get("modules") or []]
    return {
        "session_id": sid,
        "slot": session_entry.get("slot"),
        "intent": session_entry.get("intent"),
        "priority": session_entry.get("priority"),
        "location": session_entry.get("location"),
        "gym_id": session_entry.get("gym_id"),
        "tags": session_entry.get("tags") or {},
        "plan_constraints": session_entry.get("constraints_applied") or [],
        "plan_explain": session_entry.get("explain") or [],
        "session_source_path": str(_session_file(sid)),
        "resolver_trace": {
            "selected_modules": selected_modules,
            "constraints_influencing_selection": sorted(set((session_entry.get("constraints_applied") or []) + ["resolver_p0_hard_filters"])),
        },
        "resolved_blocks": (resolved.get("resolved_session") or {}).get("blocks") or [],
        "exercise_instances": (resolved.get("resolved_session") or {}).get("exercise_instances") or [],
        "resolution_status": resolved.get("resolution_status"),
    }


def preview_day(plan_path: str, date: str, user_state_path: str, out_path: str) -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[2]
    plan_file = Path(plan_path)
    state_file = Path(user_state_path)
    out_file = Path(out_path)

    plan = _read_json(plan_file)
    day = _find_day(plan, date)
    user_state = ensure_planning_defaults(_read_json(state_file))

    sessions: List[Dict[str, Any]] = [
        _resolve_single(repo_root=repo_root, session_entry=s, date_value=date, user_state=user_state)
        for s in (day.get("sessions") or [])
    ]

    artifact = {
        "resolved_day_version": "1.0",
        "resolved_ref": f"{plan_file.stem}__{date}__resolved.json",
        "date": date,
        "plan": {
            "plan_version": plan.get("plan_version"),
            "start_date": plan.get("start_date"),
            "profile_snapshot": plan.get("profile_snapshot") or {},
        },
        "day": {"weekday": day.get("weekday"), "source": str(plan_file)},
        "sessions": sessions,
        "summary": {
            "planned_session_count": len(day.get("sessions") or []),
            "resolved_session_count": len(sessions),
        },
    }
    artifact = inject_targets(artifact, user_state)
    _write_json(out_file, artifact)
    return artifact


def _normalize_feedback_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    items = payload.get("exercise_feedback_v1")
    if items is None and isinstance(payload.get("actual"), dict):
        items = payload["actual"].get("exercise_feedback_v1")
    items = items or []
    if not isinstance(items, list):
        items = []

    normalized: List[Dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        item["feedback_label"] = canonical_feedback_label(item)
        normalized.append(item)

    normalized.sort(key=lambda x: str(x.get("exercise_id") or ""))
    return {"exercise_feedback_v1": normalized}


def apply_day_feedback(
    resolved_day_path: str,
    feedback_json_path: str,
    user_state_path: str,
    log_path: str,
    out_user_state_path: Optional[str] = None,
) -> Dict[str, Any]:
    resolved_day = _read_json(Path(resolved_day_path))
    feedback = _read_json(Path(feedback_json_path))
    state = ensure_planning_defaults(_read_json(Path(user_state_path)))

    outcomes = _normalize_feedback_payload(feedback)
    status = str(feedback.get("status") or "done").strip().lower()
    if status not in {"done", "skipped"}:
        status = "done"
    log_entry = build_log_entry(resolved_day=resolved_day, status=status, outcomes=outcomes, notes=str(feedback.get("notes") or ""))
    append_jsonl(Path(log_path), log_entry)

    updated = apply_day_result_to_user_state(state, resolved_day=resolved_day, status=status)
    updated = apply_feedback(log_entry, updated)

    target_state_path = Path(out_user_state_path) if out_user_state_path else Path(user_state_path)
    _write_json(target_state_path, updated)
    return {"log_entry": log_entry, "user_state": updated}
