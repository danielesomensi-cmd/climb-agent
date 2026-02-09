# UI Day View (Gradio) — Runbook + UI Contract (Colab)

## Regola #0 (critica): in Colab NON si spezza
Se vuoi evitare gli errori “di ieri”, valgono **sempre** queste regole:

- **Ogni procedura = UNA sola cella Colab.**
- La cella deve iniziare con:
  - `%%bash` (prima riga, da solo)
  - `set -euo pipefail`
  - `cd /content/climb-agent`
- **Niente caratteri strani Unicode** copiando comandi (es. `ls -�`): usa solo comandi ASCII (`ls -la`, `cat`, `sed`, `python - <<'PY'`).
- Quando chiedi a ChatGPT un comando: scrivi **esplicitamente**
  - “Dammi **UN SOLO** blocco `%%bash` **contiguo**, non spezzato”.

> **Comando da aggiungere all’inizio (sempre):**
> - `%%bash`
> - `set -euo pipefail`
> - `cd /content/climb-agent`
>
> **Comando da aggiungere alla fine (consigliato):**
> - `echo "__DONE__"`

---

## Directory / file coinvolti (single source of truth)
- UI: `scripts/ui_day_view_gradio.py`
- Resolved sessions (smoke): `out/manual_sanity/ui_smoke_resolved__*.json`
- Log templates (obbligatori per la UI): `out/log_templates/template_*.json`
- Log main: `data/logs/session_logs.jsonl`
- Log rejected (se schema invalid): `data/logs/session_logs_rejected.jsonl`

---

## UI Contract (anti-errori)
Questa è la “contract surface” che non deve rompersi:

### A) Status: sempre schema-valid
- `exercise_outcomes[*].actual.status` **DEVE** essere uno tra:
  - `planned` | `done` | `skipped` | `modified`
- Qualsiasi valore “sporco” (tipo `10`, `0`, `""`) va normalizzato → `planned`.

### B) Parsing robusto (mai crash)
- Campi numerici: cast robusto; se blank/non numerico → default `0` (o `0.0`).
- Stringhe: trim; se blank → `""`.
- `pain_flags`: **sempre lista** (vuota se blank).
- `used_total_load_kg`: può essere calcolato come `bodyweight + used_added_weight_kg - used_assistance_kg` (se applicabile).

### C) Ordine campi: struttura unica e stabile
Per ogni riga (exercise) l’UI raccoglie **in questo ordine**:

1. `status`
2. `used_added_weight_kg`
3. `used_assistance_kg`
4. `sets_done`
5. `rpe`
6. `difficulty_label`
7. `enjoyment`
8. `notes`
9. `pain_flags`

### D) Input Gradio verso `on_append`: INTERLEAVED per riga
Il bug principale di ieri era qui: gli `inputs=[*status_dd, *added, ...]` arrivavano “a blocchi”.
Deve essere **interleaved** per riga:

`(status, added, assist, sets_done, rpe, diff, enjoy, notes, pain) * N`

---

> Note: For interactive use in Colab, start the UI in a Python cell (see docs/COLAB_START.md).
> The one-cell smoke path uses bash+nohup as an automation exception.


## SMOKE PATH MINIMO (end-to-end) — **UNA SOLA CELLE**
Questo blocco:
1) pulisce runtime,
2) genera 1 resolved session,
3) genera 1 template,
4) avvia UI,
5) verifica listener e log.

> Copia/incolla **tutto** in **una sola** cella Colab.

~~~bash
%%bash
set -euo pipefail
cd /content/climb-agent

PORT=7861

echo "== 0) Stop UI + clean runtime =="
pkill -f "scripts/ui_day_view_gradio.py" || true
rm -rf .gradio || true
mkdir -p out out/manual_sanity out/log_templates data/logs
rm -f out/ui_${PORT}.log out/ui_${PORT}.pid

echo
echo "== 1) Generate ONE resolved session json (signature-aware) =="
RESOLVED_PATH="$(python - <<'PY'
import os, sys, time, json, importlib, inspect
from pathlib import Path

repo_root = os.getcwd()
sys.path.insert(0, repo_root)

# pick a session deterministically
preferred = [
    Path("catalog/sessions/v1/deload_recovery.json"),
    Path("catalog/sessions/v1/strength_long.json"),
]
session_path = None
for p in preferred:
    if p.is_file():
        session_path = str(p)
        break
if session_path is None:
    cands = sorted(Path("catalog/sessions").rglob("*.json"))
    if not cands:
        raise SystemExit("ERROR: no session json under catalog/sessions/")
    session_path = str(cands[0])

out_path = Path("out/manual_sanity") / f"ui_smoke_resolved__{int(time.time())}.json"
out_path.parent.mkdir(parents=True, exist_ok=True)

# minimal context
context = {
    "location": "home",
    "gym_id": None,
    "available_equipment": ["hangboard","pullup_bar","dumbbell","band","weight"],
}

mod = importlib.import_module("catalog.engine.resolve_session")
fn = getattr(mod, "resolve_session")
sig = inspect.signature(fn)
params = sig.parameters

templates_dir = "catalog/templates"
exercises_path = "catalog/exercises/v1/exercises.json"

kwargs = {}
# required positional-ish params (support different naming)
if "repo_root" in params: kwargs["repo_root"] = repo_root
elif "root" in params: kwargs["root"] = repo_root
elif "repo" in params: kwargs["repo"] = repo_root

if "session_path" in params: kwargs["session_path"] = session_path
elif "session" in params: kwargs["session"] = session_path
elif "session_file" in params: kwargs["session_file"] = session_path
elif "session_json_path" in params: kwargs["session_json_path"] = session_path
elif "session_id" in params: kwargs["session_id"] = Path(session_path).stem

# signature you saw: (repo_root, session_path, templates_dir, exercises_path, out_path, *)
if "templates_dir" in params: kwargs["templates_dir"] = templates_dir
if "exercises_path" in params: kwargs["exercises_path"] = exercises_path
if "out_path" in params: kwargs["out_path"] = str(out_path)

# optional context naming
if "context" in params: kwargs["context"] = context
elif "resolver_context" in params: kwargs["resolver_context"] = context
elif "ctx" in params: kwargs["ctx"] = context

# force writing if supported
if "write_output" in params: kwargs["write_output"] = True

res = fn(**kwargs)
# if resolver didn't write, write ourselves
if not out_path.exists():
    out_path.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")

print(str(out_path), end="")
PY
)"
echo "$RESOLVED_PATH"
test -f "$RESOLVED_PATH"

echo
echo "== 2) Generate ONE log template =="
TEMPLATE_PATH="out/log_templates/template_$(date +%s).json"
python -u scripts/generate_log_template.py \
  --resolved_session_path "$RESOLVED_PATH" \
  --out_path "$TEMPLATE_PATH" \
  --overwrite
echo "$TEMPLATE_PATH"
test -f "$TEMPLATE_PATH"

echo
echo "== 3) Start UI on :$PORT =="
nohup python -u scripts/ui_day_view_gradio.py --server_port "$PORT" > "out/ui_${PORT}.log" 2>&1 &
PID=$!
echo "$PID" > "out/ui_${PORT}.pid"
echo "UI PID=$PID"

echo
echo "== 4) Wait up to 120s for listener (or exit) =="
for i in $(seq 1 120); do
  if ss -ltnp 2>/dev/null | grep -q ":$PORT"; then
    echo "LISTENING on :$PORT after ${i}s ✅"
    ss -ltnp 2>/dev/null | grep ":$PORT" || true
    break
  fi
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "PROCESS EXITED early at ${i}s ❌"
    tail -n 200 "out/ui_${PORT}.log" || true
    exit 1
  fi
  sleep 1
done

if ! ss -ltnp 2>/dev/null | grep -q ":$PORT"; then
  echo "Still NOT LISTENING after 120s ❌"
  tail -n 200 "out/ui_${PORT}.log" || true
  exit 1
fi

echo
echo "== 5) Log checks =="
echo "-- main (last line) --"
tail -n 1 data/logs/session_logs.jsonl | python -m json.tool || true
echo "-- rejected (if any) --"
if [ -f data/logs/session_logs_rejected.jsonl ]; then
  tail -n 1 data/logs/session_logs_rejected.jsonl | python -m json.tool || true
else
  echo "no rejected file ✅"
fi

echo "__DONE__"
~~~

---

## Quick debug (1 cell per comando)
Se qualcosa non torna, usa **una cella per volta**.

~~~bash
%%bash
set -euo pipefail
cd /content/climb-agent
ls -la data/logs out/log_templates out/manual_sanity | sed -n '1,200p'
echo "__DONE__"
~~~

~~~bash
%%bash
set -euo pipefail
cd /content/climb-agent
python -m py_compile scripts/ui_day_view_gradio.py
tail -n 120 out/ui_7861.log || true
echo "__DONE__"
~~~

---

## Git: quando tutto gira, fai commit/push
Regola pratica: **committa solo quando** (a) UI compila, (b) smoke path end-to-end OK, (c) log main scritto senza rejected.

~~~bash
%%bash
set -euo pipefail
cd /content/climb-agent
git status --porcelain
git diff --stat
echo "__DONE__"
~~~

