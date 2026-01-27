from __future__ import annotations

# --- guardrail: ensure running from repo root (Colab common pitfall) ---
from pathlib import Path as _Path
_REPO_ROOT = _Path(__file__).resolve().parents[1]
# ---------------------------------------------------------------

# --- DEBUG PREAMBLE (AUTO; remove after) ---
import faulthandler as _faulthandler
_faulthandler.enable()
_faulthandler.dump_traceback_later(20, repeat=True)
print('UI DEBUG: boot', flush=True)
# --- END DEBUG PREAMBLE ---


import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple
def pick_log_path() -> Path:
    p1 = Path("data/logs/sessions_2026.jsonl")
    p2 = Path("data/logs/session_logs.jsonl")
    return p1 if p1.exists() else p2

def pick_rejected_path() -> Path:
    return Path("data/logs/session_logs_rejected.jsonl")

def latest_template_path() -> Path | None:
    root = Path("out/log_templates")
    if not root.exists():
        return None
    files = sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None

def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def tail_jsonl(path: Path, n: int = 1) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    out = []
    for ln in lines[-n:]:
        out.append(json.loads(ln))
    return out

def run_append(entry: Dict[str, Any], log_path: Path, rejected_path: Path) -> Tuple[int, str, str]:
    # write temp json
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False)
        tmp = f.name

    try:
        cmd = [
            sys.executable,
            "scripts/append_session_log.py",
            "--repo_root", ".",
            "--log_template_path", tmp,
            "--log_path", str(log_path),
            "--rejected_log_path", str(rejected_path),
        ]
        p = subprocess.run(cmd, capture_output=True, text=True)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass

def try_quote() -> str:
    # optional: if quote selector exists, show deterministic quote of today
    qsel = Path("scripts/select_quote.py")
    quotes = Path("motivation/quotes.json")
    if not (qsel.exists() and quotes.exists()):
        return ""
    cmd = [
        sys.executable, "scripts/select_quote.py",
        "--date", date.today().isoformat(),
        "--cycle_id", "2026Q1",
        "--phase", "strength",
        "--day_type", "training",
        "--language", "it",
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        return ""
    try:
        q = json.loads(p.stdout.strip())
        return f'“{q.get("text","")}” — {q.get("author","")}'
    except Exception:
        return ""

def planned_summary(outcome: Dict[str, Any]) -> str:
    planned = outcome.get("planned") or {}
    # keep short; UI-0
    if isinstance(planned, dict):
        pres = planned.get("prescription") or {}
        if isinstance(pres, dict):
            sets = pres.get("sets")
            reps = pres.get("reps")
            secs = pres.get("seconds")
            parts = []
            if sets is not None: parts.append(f"sets={sets}")
            if reps is not None: parts.append(f"reps={reps}")
            if secs is not None: parts.append(f"sec={secs}")
            return ", ".join(parts)
    return ""

def build_entry_from_form(template: Dict[str, Any], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    entry = json.loads(json.dumps(template))  # deep copy
    outs = entry.get("exercise_outcomes") or []
    if not isinstance(outs, list):
        return entry

    for i, o in enumerate(outs):
        if not isinstance(o, dict):
            continue
        actual = o.get("actual") or {}
        if not isinstance(actual, dict):
            actual = {}
        r = rows[i]

        actual["status"] = r["status"]

        # numeric fields: only set if provided
        for k in ["used_added_weight_kg", "used_assistance_kg", "sets_done", "rpe", "enjoyment"]:
            v = r.get(k)
            if v is None or v == "":
                continue
            actual[k] = float(v) if k in ("used_added_weight_kg","used_assistance_kg","rpe","enjoyment") else int(v)

        if r.get("difficulty_label"):
            actual["difficulty_label"] = r["difficulty_label"]
        if r.get("notes"):
            actual["notes"] = r["notes"]

        # pain flags: comma-separated -> list
        pf = r.get("pain_flags","").strip()
        if pf:
            actual["pain_flags"] = [x.strip() for x in pf.split(",") if x.strip()]

        o["actual"] = actual
        outs[i] = o

    entry["exercise_outcomes"] = outs
    return entry

def main():
    print('UI: start main()', flush=True)

    ap = argparse.ArgumentParser()
    ap.add_argument("--log_path", default=None)
    ap.add_argument("--rejected_log_path", default=None)
    ap.add_argument("--server_port", type=int, default=7860)
    args = ap.parse_args()

    print('UI: importing gradio...', flush=True)
    import gradio as gr
    print('UI: gradio imported', flush=True)


    log_path = Path(args.log_path) if args.log_path else pick_log_path()
    rejected_path = Path(args.rejected_log_path) if args.rejected_log_path else pick_rejected_path()

    print('UI: locating latest template...', flush=True)
    tpath = latest_template_path()
    if not tpath:
        raise SystemExit("No templates found in out/log_templates/. Run generate_log_template first.")

    print(f'UI: loading template: {tpath}', flush=True)
    template = load_json(tpath)
    outcomes = template.get("exercise_outcomes") or []
    if not isinstance(outcomes, list) or not outcomes:
        raise SystemExit("Template has no exercise_outcomes.")

    quote = try_quote()

    with gr.Blocks(title="climb-agent — Day View (UI-0)") as demo:
        gr.Markdown("# climb-agent — Day View (UI-0)")
        gr.Markdown(f"**Template:** `{tpath}`")
        gr.Markdown(f"**Log path:** `{log_path}`  \n**Rejected:** `{rejected_path}`")
        if quote:
            gr.Markdown(f"### Quote\n{quote}")

        gr.Markdown("## Log actual")

        status_dd = []
        added = []
        assist = []
        sets_done = []
        rpe = []
        diff = []
        enjoy = []
        notes = []
        pain = []

        for i, o in enumerate(outcomes):
            ex_id = o.get("exercise_id","")
            summ = planned_summary(o)
            gr.Markdown(f"### {i+1}. `{ex_id}`  \n_planned: {summ}_")

            status_dd.append(gr.Dropdown(
                choices=["planned","done","skipped","modified"],
                value="done",
                label="status"
            ))
            added.append(gr.Number(value=None, label="used_added_weight_kg (optional)"))
            assist.append(gr.Number(value=None, label="used_assistance_kg (optional)"))
            sets_done.append(gr.Number(value=None, label="sets_done (optional)"))
            rpe.append(gr.Number(value=None, label="rpe (0-10, optional)"))
            diff.append(gr.Textbox(value="", label="difficulty_label (optional)"))
            enjoy.append(gr.Number(value=None, label="enjoyment (0-10, optional)"))
            notes.append(gr.Textbox(value="", label="notes (optional)", lines=2))
            pain.append(gr.Textbox(value="", label="pain_flags (comma-separated, optional)"))

        btn = gr.Button("Validate + Append (S3)")

        out_status = gr.Markdown("")
        out_last = gr.JSON(label="Last log entry (main)")
        out_stats = gr.JSON(label="Mini stats (last 50)")

        def on_append(*vals):
            # vals comes grouped by components order above
            n = len(outcomes)
            rows = []
            idx = 0
            for i in range(n):
                row = {"status": vals[idx]}
                idx += 1
                row["used_added_weight_kg"] = vals[idx]; idx += 1
                row["used_assistance_kg"] = vals[idx]; idx += 1
                row["sets_done"] = vals[idx]; idx += 1
                row["rpe"] = vals[idx]; idx += 1
                row["difficulty_label"] = vals[idx]; idx += 1
                row["enjoyment"] = vals[idx]; idx += 1
                row["notes"] = vals[idx]; idx += 1
                row["pain_flags"] = vals[idx]; idx += 1
                rows.append(row)

            entry = build_entry_from_form(template, rows)
            rc, so, se = run_append(entry, log_path, rejected_path)

            if rc == 0:
                msg = "✅ Appended to main log."
            else:
                msg = f"❌ Quarantined (rc={rc}). See errors below."

            tail = tail_jsonl(log_path, n=1)
            last = tail[0] if tail else {}

            # call mini analytics
            p = subprocess.run(
                [sys.executable, "scripts/mini_analytics.py", "--log_path", str(log_path), "--last_n", "50"],
                capture_output=True, text=True
            )
            stats = {}
            if p.returncode == 0:
                try:
                    stats = json.loads(p.stdout)
                except Exception:
                    stats = {"error": "failed to parse analytics output"}
            else:
                stats = {"error": p.stderr.strip()}

            details = ""
            if se:
                details = "\n\n```\n" + se + "\n```"
            return msg + details, last, stats

        btn.click(
            fn=on_append,
            inputs=[*status_dd, *added, *assist, *sets_done, *rpe, *diff, *enjoy, *notes, *pain],
            outputs=[out_status, out_last, out_stats]
        )

    print('UI: launching gradio server...', flush=True)
    demo.launch(
        server_name='127.0.0.1',
        server_port=args.server_port,
        share=False,
        show_error=True,
        prevent_thread_lock=False,
    )
if __name__ == "__main__":
    main()
