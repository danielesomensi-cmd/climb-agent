from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import gradio as gr

from catalog.engine.daily_loop import apply_day_feedback, preview_day


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TMP_ROOT = Path(tempfile.gettempdir()) / "climb-agent-daily-loop"


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _pretty(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def _default_paths(use_real_paths: bool) -> Tuple[Path, Path]:
    if use_real_paths:
        return REPO_ROOT / "data/user_state.json", REPO_ROOT / "data/logs/sessions_2026.jsonl"
    DEFAULT_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    return DEFAULT_TMP_ROOT / "user_state.json", DEFAULT_TMP_ROOT / "sessions.jsonl"


def _ensure_tmp_user_state(path: Path) -> None:
    if path.exists():
        return
    source = REPO_ROOT / "data/user_state.json"
    path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


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


def _preview(plan_path: str, date_value: str, use_real_paths: bool) -> Tuple[List[Dict[str, Any]], str, str, str]:
    user_state_path, log_path = _default_paths(use_real_paths)
    if not use_real_paths:
        _ensure_tmp_user_state(user_state_path)

    out_resolved = DEFAULT_TMP_ROOT / f"resolved_{date_value}.json"
    preview = preview_day(plan_path=plan_path, date=date_value, user_state_path=str(user_state_path), out_path=str(out_resolved))
    rows = _collect_rows(preview)
    return rows, _pretty(preview), str(user_state_path), str(log_path)


def _apply(rows: List[Dict[str, Any]], resolved_json: str, user_state_path: str, log_path: str) -> Tuple[str, str]:
    resolved = json.loads(resolved_json)
    resolved_path = DEFAULT_TMP_ROOT / "resolved_from_ui.json"
    resolved_path.write_text(_pretty(resolved), encoding="utf-8")

    feedback = {"status": "done", "exercise_feedback_v1": []}
    for row in rows or []:
        item = {
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

    feedback["exercise_feedback_v1"].sort(key=lambda x: str(x.get("exercise_id") or ""))
    feedback_path = DEFAULT_TMP_ROOT / "feedback_from_ui.json"
    feedback_path.write_text(_pretty(feedback), encoding="utf-8")

    result = apply_day_feedback(
        resolved_day_path=str(resolved_path),
        feedback_json_path=str(feedback_path),
        user_state_path=user_state_path,
        log_path=log_path,
        out_user_state_path=user_state_path,
    )
    return _pretty(result["log_entry"]), _pretty(result["user_state"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Gradio UI for deterministic daily loop")
    parser.add_argument("--server_port", type=int, default=7862)
    args = parser.parse_args()

    with gr.Blocks(title="Climb Agent Daily Loop") as demo:
        gr.Markdown("## Day view (daily loop)\nDefault paths are in /tmp for safe smoke tests.")

        with gr.Row():
            plan = gr.Textbox(label="Plan path", value="out/plans/plan_week.json")
            date_value = gr.Textbox(label="Date (YYYY-MM-DD)")
            use_real_paths = gr.Checkbox(label="Use real paths (data/user_state + data/logs)", value=False)

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
        user_state_path = gr.Textbox(label="User state path")
        log_path = gr.Textbox(label="Log path")

        apply_btn = gr.Button("Apply feedback")
        log_json = gr.Code(label="Appended log entry", language="json")
        updated_state_json = gr.Code(label="Updated user state", language="json")

        preview_btn.click(_preview, inputs=[plan, date_value, use_real_paths], outputs=[rows, resolved_json, user_state_path, log_path])
        apply_btn.click(_apply, inputs=[rows, resolved_json, user_state_path, log_path], outputs=[log_json, updated_state_json])

    demo.launch(server_port=args.server_port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
