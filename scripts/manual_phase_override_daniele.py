"""One-shot: override Endurance Base 4→2 per Daniele.

Brief: B254. Run once, then archive in _archive/scripts/.

Context (2026-05-20):
- Daniele è in week 1 del macrociclo lead 8a+ (start_date 2026-05-18, total_weeks 12).
- Vuole accorciare Endurance Base 4→2 settimane perché tornato fresco da un macrociclo
  precedente; non vuole 4w di solo aerobico.
- Surplus +2 redistribuito a strength_power (+1) e power_endurance (+1).
- total_weeks invariato (12). Deadline invariata (2026-08-09).

Past-sessions immutable:
- week_plans[2026-05-18] (week 1, 3 sessioni con status='done': lun boulder + mar
  conditioning + mar test_max_hang_7s) → preservato intatto
- week_plans[2026-05-25] (week 2, futura ma base in entrambi i piani) → preservato

Engine note:
- base=2 viola _PHASE_FLOORS_LEAD['base']=4. Override manuale esplicito, bypassa
  _compute_phase_durations(). GET /api/week/{N} legge macrocycle.phases[].duration_weeks
  via week_num_to_phase_context() senza ri-validare → l'override sopravvive a runtime.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# ── Bootstrap env + persistence backend ──────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Load .env into os.environ
env_path = REPO_ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

os.environ["STORAGE_BACKEND"] = "supabase"

from backend.engine import storage  # noqa: E402

# ── Constants ────────────────────────────────────────────────────────────────
USER_ID = "7ea9f0ee-e629-4ce9-8f4f-f8e6e3dc771e"

NEW_DURATIONS = {
    "base": 2,
    "strength_power": 4,
    "power_endurance": 3,
    "performance": 2,
    "deload": 1,
}
# Computed start_week per phase (1-based, sequential)
NEW_START_WEEKS = {
    "base": 1,
    "strength_power": 3,
    "power_endurance": 7,
    "performance": 10,
    "deload": 12,
}
EXPECTED_TOTAL = 12


def main() -> int:
    print("=== B254: manual phase override Daniele ===")
    print(f"USER_ID: {USER_ID}")
    print(f"STORAGE_BACKEND: {os.environ['STORAGE_BACKEND']}")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print()

    # ── 1. Read state ────────────────────────────────────────────────────────
    state = storage.read_state(USER_ID)
    if not state:
        print("ERROR: no state for user", file=sys.stderr)
        return 2

    mc = state.get("macrocycle") or {}
    phases = mc.get("phases") or []
    if not phases:
        print("ERROR: macrocycle has no phases", file=sys.stderr)
        return 2

    total_before = sum(p.get("duration_weeks", 0) for p in phases)
    print(f"Macrocycle: start_date={mc.get('start_date')}  total_weeks={mc.get('total_weeks')}  end_date={mc.get('end_date')}")
    print(f"Discipline: {(mc.get('goal') or state.get('goal') or {}).get('discipline')}")
    print()
    print("=== PHASES BEFORE ===")
    for p in phases:
        print(f"  {p['phase_id']:18s} duration_weeks={p['duration_weeks']}  start_week={p['start_week']}  end_week={p.get('end_week')}")
    print(f"  TOTAL: {total_before}")
    print()

    if total_before != EXPECTED_TOTAL:
        print(f"ERROR: expected total {EXPECTED_TOTAL}, got {total_before}", file=sys.stderr)
        return 3

    # ── 2. Backup ────────────────────────────────────────────────────────────
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    backup_path = REPO_ROOT / "_archive" / "data_backups" / f"daniele_pre_B254_{ts}.json"
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    print(f"Backup written → {backup_path.relative_to(REPO_ROOT)}")
    print()

    # ── 3. Patch phases in-place (preserve all other keys) ───────────────────
    seen_ids = set()
    for p in phases:
        pid = p["phase_id"]
        if pid not in NEW_DURATIONS:
            print(f"ERROR: unexpected phase_id {pid!r}", file=sys.stderr)
            return 4
        if pid in seen_ids:
            print(f"ERROR: duplicate phase_id {pid!r}", file=sys.stderr)
            return 4
        seen_ids.add(pid)
        new_dur = NEW_DURATIONS[pid]
        new_start = NEW_START_WEEKS[pid]
        new_end = new_start + new_dur - 1
        p["duration_weeks"] = new_dur
        p["start_week"] = new_start
        p["end_week"] = new_end

    if seen_ids != set(NEW_DURATIONS.keys()):
        missing = set(NEW_DURATIONS) - seen_ids
        print(f"ERROR: missing expected phase_ids {missing}", file=sys.stderr)
        return 4

    total_after = sum(p["duration_weeks"] for p in phases)
    if total_after != EXPECTED_TOTAL:
        print(f"ERROR: post-patch total {total_after} != {EXPECTED_TOTAL}", file=sys.stderr)
        return 5

    # ── 4. Invalidate week_plans for weeks ≥ 3 in current cycle ──────────────
    # week_plans is keyed by Monday YYYY-MM-DD. Compute the cutoff: any entry
    # whose date >= (start_date + 14d) AND <= end_date belongs to weeks 3+ of
    # the current cycle and must be regenerated against the new phase mapping.
    week_plans = state.get("week_plans") or {}
    start_iso = mc.get("start_date")
    end_iso = mc.get("end_date")
    cutoff_iso = None
    invalidated = []
    if start_iso:
        start_dt = datetime.strptime(start_iso, "%Y-%m-%d").date()
        from datetime import timedelta
        cutoff_dt = start_dt + timedelta(days=14)
        cutoff_iso = cutoff_dt.isoformat()
        for key in list(week_plans.keys()):
            # Only invalidate keys IN the current macrocycle range; pre-cycle
            # residue from previous macrocycles must stay untouched.
            in_range = (key >= start_iso) and (end_iso is None or key <= end_iso)
            if in_range and key >= cutoff_iso:
                invalidated.append(key)
                del week_plans[key]

    print("=== WEEK_PLANS ACTION ===")
    print(f"  cutoff (start_date + 14d): {cutoff_iso}")
    preserved_in_cycle = sorted(k for k in week_plans if start_iso and k >= start_iso and (end_iso is None or k <= end_iso))
    print(f"  preserved IN cycle: {preserved_in_cycle}")
    print(f"  invalidated:        {invalidated if invalidated else '(none)'}")
    print()

    # ── 5. Write state ───────────────────────────────────────────────────────
    storage.write_state(state, USER_ID)
    print("State written to Supabase.")
    print()

    # ── 6. Reload and verify ─────────────────────────────────────────────────
    reloaded = storage.read_state(USER_ID)
    rphases = (reloaded.get("macrocycle") or {}).get("phases") or []
    print("=== PHASES AFTER (reload) ===")
    for p in rphases:
        print(f"  {p['phase_id']:18s} duration_weeks={p['duration_weeks']}  start_week={p['start_week']}  end_week={p['end_week']}")
    print(f"  TOTAL: {sum(p['duration_weeks'] for p in rphases)}")

    # Assertions
    for pid, expected_dur in NEW_DURATIONS.items():
        actual = next((p for p in rphases if p["phase_id"] == pid), None)
        assert actual is not None, f"phase {pid} missing after reload"
        assert actual["duration_weeks"] == expected_dur, f"{pid}: {actual['duration_weeks']} != {expected_dur}"
        assert actual["start_week"] == NEW_START_WEEKS[pid], f"{pid}: start_week mismatch"

    print()
    print("=== DONE — patch applied + verified ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
