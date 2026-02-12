from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import gradio as gr
except ModuleNotFoundError:  # pragma: no cover - optional dependency in some test envs
    gr = None

from catalog.engine.daily_loop import apply_day_feedback, preview_day


DEFAULT_TMP_ROOT = Path(tempfile.gettempdir()) / "climb-agent-daily-loop"
DEFAULT_PLAN_PATH = "out/plans/plan_week.json"
DEFAULT_USER_STATE_PATH = "/tmp/user_state.json"
DEFAULT_LOG_PATH = "/tmp/closed_loop.jsonl"


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _pretty(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def _default_paths(use_real_paths: bool) -> Tuple[str, str]:
    if use_real_paths:
        return str(REPO_ROOT / "data/user_state.json"), str(REPO_ROOT / "data/logs/sessions_2026.jsonl")
    return DEFAULT_USER_STATE_PATH, DEFAULT_LOG_PATH


def _ensure_tmp_user_state(path: Path) -> None:
    if path.exists():
        return
    source = REPO_ROOT / "data/user_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def _seed_tmp() -> str:
    source = REPO_ROOT / "data/user_state.json"
    user_state = Path(DEFAULT_USER_STATE_PATH)
    log_path = Path(DEFAULT_LOG_PATH)
    user_state.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, user_state)
    log_path.write_text("", encoding="utf-8")
    return "Seeded /tmp (user_state + closed_loop log reset)."


def _collect_rows(resolved_day: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for session in resolved_day.get("sessions") or []:
        for inst in session.get("exercise_instances") or []:
            rows.append({
                "session_id": session.get("session_id"),
                "exercise_id": inst.get("exercise_id"),
                "feedback_label": "ok",
                "completed": True,
                "used_total_load_kg": "",
                "used_external_load_kg": "",
                "used_grade": "",
                "surface_selected": "",
                "status": "done",
                "notes": "",
            })
    rows.sort(key=lambda x: (str(x.get("session_id") or ""), str(x.get("exercise_id") or "")))
    return rows


def _preview(
    plan_path: str,
    date_value: str,
    user_state_path: str,
    log_path: str,
    use_real_paths: bool,
) -> Tuple[List[Dict[str, Any]], str, str, str, str]:
    try:
        selected_user_state, selected_log = _default_paths(use_real_paths)
        selected_user_state = selected_user_state if use_real_paths else (user_state_path.strip() or DEFAULT_USER_STATE_PATH)
        selected_log = selected_log if use_real_paths else (log_path.strip() or DEFAULT_LOG_PATH)

        state_path = Path(selected_user_state)
        if not use_real_paths:
            _ensure_tmp_user_state(state_path)

        DEFAULT_TMP_ROOT.mkdir(parents=True, exist_ok=True)
        safe_date = date_value.strip() or "no_date"
        out_resolved = DEFAULT_TMP_ROOT / f"resolved_{safe_date}.json"
        preview = preview_day(
            plan_path=plan_path,
            date=date_value,
            user_state_path=str(state_path),
            out_path=str(out_resolved),
        )
        rows = _collect_rows(preview)
        return rows, _pretty(preview), str(selected_user_state), str(selected_log), ""
    except Exception:
        return [], "", user_state_path, log_path, traceback.format_exc()


def _apply(
    rows: List[Dict[str, Any]],
    resolved_json: str,
    user_state_path: str,
    log_path: str,
) -> Tuple[str, str, str]:
    try:
        resolved = json.loads(resolved_json)
        DEFAULT_TMP_ROOT.mkdir(parents=True, exist_ok=True)
        resolved_path = DEFAULT_TMP_ROOT / "resolved_from_ui.json"
        resolved_path.write_text(_pretty(resolved), encoding="utf-8")

        feedback = {"status": "done", "exercise_feedback_v1": []}
        for row in rows or []:
            item = {
                "session_id": row.get("session_id"),
                "exercise_id": row.get("exercise_id"),
                "feedback_label": row.get("feedback_label") or "ok",
                "completed": bool(row.get("completed")),
                "status": row.get("status") or "done",
            }
            for key in ("used_total_load_kg", "used_external_load_kg"):
                value = row.get(key)
                if value not in (None, ""):
                    item[key] = float(value)
            for key in ("used_grade", "surface_selected", "notes"):
                value = row.get(key)
                if value not in (None, ""):
                    item[key] = value
            feedback["exercise_feedback_v1"].append(item)

        feedback["exercise_feedback_v1"].sort(key=lambda x: (str(x.get("session_id") or ""), str(x.get("exercise_id") or "")))
        feedback_path = DEFAULT_TMP_ROOT / "feedback_from_ui.json"
        feedback_path.write_text(_pretty(feedback), encoding="utf-8")

        result = apply_day_feedback(
            resolved_day_path=str(resolved_path),
            feedback_json_path=str(feedback_path),
            user_state_path=user_state_path,
            log_path=log_path,
            out_user_state_path=user_state_path,
        )
        return _pretty(result["log_entry"]), _pretty(result["user_state"]), ""
    except Exception:
        return "", "", traceback.format_exc()


def main() -> int:
    if gr is None:
        raise ModuleNotFoundError("gradio is required to run scripts/ui_daily_loop_gradio.py")

    parser = argparse.ArgumentParser(description="Gradio UI for deterministic daily loop")
    parser.add_argument("--server_port", type=int, default=7862)
    args = parser.parse_args()

    with gr.Blocks(title="Climb Agent Daily Loop") as demo:
        gr.Markdown("## Day view (daily loop)\nDefault paths are in /tmp for safe smoke tests.")

        with gr.Row():
            plan = gr.Textbox(label="Plan path", value=DEFAULT_PLAN_PATH)
            date_value = gr.Textbox(label="Date (YYYY-MM-DD)", value="")
            use_real_paths = gr.Checkbox(label="Use real paths (data/user_state + data/logs)", value=False)
        with gr.Row():
            user_state_path = gr.Textbox(label="User state path", value=DEFAULT_USER_STATE_PATH)
            log_path = gr.Textbox(label="Log path", value=DEFAULT_LOG_PATH)
        seed_btn = gr.Button("Seed /tmp")
        seed_status = gr.Textbox(label="Seed status", interactive=False)

        preview_btn = gr.Button("Preview day")
        rows = gr.Dataframe(
            headers=[
                "session_id",
                "exercise_id",
                "feedback_label",
                "completed",
                "used_total_load_kg",
                "used_external_load_kg",
                "used_grade",
                "surface_selected",
                "status",
                "notes",
            ],
            datatype=["str", "str", "str", "bool", "str", "str", "str", "str", "str", "str"],
            row_count=(0, "dynamic"),
            col_count=(10, "fixed"),
            label="Exercise feedback",
        )
        resolved_json = gr.Code(label="Resolved day", language="json")
        with gr.Accordion("Errors", open=False):
            errors = gr.Textbox(label="Traceback", lines=14, interactive=False)

        apply_btn = gr.Button("Apply feedback")
        log_json = gr.Code(label="Appended log entry", language="json")
        updated_state_json = gr.Code(label="Updated user state", language="json")

        seed_btn.click(_seed_tmp, inputs=[], outputs=[seed_status])
        preview_btn.click(
            _preview,
            inputs=[plan, date_value, user_state_path, log_path, use_real_paths],
            outputs=[rows, resolved_json, user_state_path, log_path, errors],
        )
        apply_btn.click(_apply, inputs=[rows, resolved_json, user_state_path, log_path], outputs=[log_json, updated_state_json, errors])

    demo.launch(server_port=args.server_port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
