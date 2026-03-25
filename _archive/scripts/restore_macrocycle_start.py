#!/usr/bin/env python3
"""P0 restore: fix macrocycle start_date after equipment-regen bug.

The bug reset the macrocycle to week 1 (start_date = this_monday).
This script patches start_date back to the original value and
triggers an incremental regen to rebuild phase boundaries correctly.

Usage:
    # Local dev (default)
    python scripts/restore_macrocycle_start.py

    # Production
    python scripts/restore_macrocycle_start.py --base-url https://web-production-fb1e9.up.railway.app --user-id YOUR_UUID
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ORIGINAL_START = "2026-02-24"
ORIGINAL_TOTAL_WEEKS = 12


def api(base: str, method: str, path: str, body: dict | None = None, user_id: str | None = None) -> dict:
    url = f"{base}{path}"
    headers = {"Content-Type": "application/json"}
    if user_id:
        headers["X-User-ID"] = user_id
    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        print(f"  ERROR {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Restore macrocycle start_date after P0 bug")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--user-id", default=None)
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    uid = args.user_id

    print("=== Phase 3: Restore macrocycle ===\n")

    # 1. Read current state
    print("1. Reading current state...")
    state = api(base, "GET", "/api/state", user_id=uid)
    mc = state.get("macrocycle")
    if not mc:
        print("  No macrocycle in state — nothing to restore.")
        sys.exit(0)

    print(f"  Current start_date:  {mc['start_date']}")
    print(f"  Expected start_date: {ORIGINAL_START}")
    completion_log = state.get("session_completion_log", [])
    print(f"  session_completion_log entries: {len(completion_log)}")
    for entry in completion_log:
        print(f"    {entry['date']} | {entry['session_id']} | {entry['status']}")

    # 2. Patch start_date and end_date
    if mc["start_date"] != ORIGINAL_START:
        print(f"\n2. Patching start_date → {ORIGINAL_START}...")
        start = datetime.strptime(ORIGINAL_START, "%Y-%m-%d").date()
        total_weeks = mc.get("total_weeks", ORIGINAL_TOTAL_WEEKS)
        end = start + timedelta(weeks=total_weeks)
        api(base, "PUT", "/api/state", body={
            "macrocycle": {
                "start_date": ORIGINAL_START,
                "end_date": end.isoformat(),
            }
        }, user_id=uid)
        print(f"  ✓ start_date={ORIGINAL_START}, end_date={end.isoformat()}")
    else:
        print("\n2. start_date already correct — skipping patch.")

    # 3. Incremental regen to rebuild phase boundaries
    print("\n3. Incremental regen (from_phase=current)...")
    result = api(base, "POST", "/api/macrocycle/generate", body={
        "from_phase": "current",
    }, user_id=uid)
    new_mc = result["macrocycle"]
    print(f"  ✓ start_date={new_mc['start_date']}, total_weeks={new_mc['total_weeks']}")
    print(f"  Phases: {[p['phase_id'] for p in new_mc['phases']]}")

    # 4. Regenerate current week
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    print(f"\n4. Regenerating current week (preserve_before={tomorrow})...")
    week_data = api(base, "GET", f"/api/week/0?force=true&preserve_before={tomorrow}", user_id=uid)
    print(f"  ✓ week_num={week_data['week_num']}, phase={week_data['phase_id']}")

    # 5. Verify
    print("\n5. Verification...")
    final_state = api(base, "GET", "/api/state", user_id=uid)
    final_mc = final_state["macrocycle"]
    final_log = final_state.get("session_completion_log", [])

    assert final_mc["start_date"] == ORIGINAL_START, f"start_date mismatch: {final_mc['start_date']}"
    assert len(final_log) == len(completion_log), f"completion_log lost entries: {len(final_log)} vs {len(completion_log)}"

    print(f"  ✓ start_date = {final_mc['start_date']}")
    print(f"  ✓ completion_log entries = {len(final_log)} (preserved)")
    print(f"  ✓ Current week = {week_data['week_num']} (phase: {week_data['phase_id']})")

    # Check week 1 and 2 are accessible
    print("\n6. Verifying past weeks...")
    for wn in (1, 2):
        wd = api(base, "GET", f"/api/week/{wn}", user_id=uid)
        print(f"  Week {wn}: phase={wd['phase_id']}, days={len(wd['week_plan']['weeks'][0]['days'])}")

    print("\n=== Restore complete ===")


if __name__ == "__main__":
    main()
