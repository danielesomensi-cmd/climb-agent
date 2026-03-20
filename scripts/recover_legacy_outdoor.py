#!/usr/bin/env python3
"""D134: Investigate and recover outdoor logs stored under '__legacy__' in Supabase.

READ-ONLY by default — prints a report of what it finds.
Pass --apply to actually reassign data (requires confirmation).

Usage:
    # Dry run (default):
    python scripts/recover_legacy_outdoor.py

    # Apply reassignment:
    python scripts/recover_legacy_outdoor.py --apply --target-user USER_ID
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Ensure repo root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> None:
    parser = argparse.ArgumentParser(description="D134: recover legacy outdoor logs")
    parser.add_argument("--apply", action="store_true", help="Actually reassign data")
    parser.add_argument("--target-user", type=str, help="User ID to reassign data to")
    args = parser.parse_args()

    # Check Supabase env vars
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
        print("Run with: SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python scripts/recover_legacy_outdoor.py")
        sys.exit(1)

    from supabase import create_client
    sb = create_client(url, key)

    print("=" * 60)
    print("D134 LEGACY OUTDOOR LOG RECOVERY")
    print("=" * 60)

    # 1. Query outdoor_logs under __legacy__
    print("\n1. Checking outdoor_logs for user_id = '__legacy__'...")
    r = sb.table("outdoor_logs").select("*").eq("user_id", "__legacy__").order("session_date").execute()
    legacy_entries = r.data

    if not legacy_entries:
        print("   No outdoor_logs found under '__legacy__'. Nothing to recover.")
    else:
        print(f"   Found {len(legacy_entries)} entries under '__legacy__':")
        for entry in legacy_entries:
            e = entry.get("entry", {})
            print(f"   - {entry['session_date']} | {e.get('spot_name', '?')} | "
                  f"{e.get('discipline', '?')} | {len(e.get('routes', []))} routes | "
                  f"{e.get('duration_minutes', '?')} min")

    # 2. List all known users
    print("\n2. Known users in Supabase:")
    users_r = sb.table("users").select("user_id, clerk_id").order("user_id").execute()
    users = [u for u in users_r.data if u["user_id"] != "__legacy__"]
    for u in users:
        print(f"   - {u['user_id']} (clerk: {u.get('clerk_id', 'N/A')})")

    if not users:
        print("   No users found (besides __legacy__).")

    # 3. Check outdoor_logs for each real user
    print("\n3. Outdoor logs per user:")
    for u in users:
        uid = u["user_id"]
        ol_r = sb.table("outdoor_logs").select("session_date, entry").eq("user_id", uid).order("session_date").execute()
        entries = ol_r.data
        if entries:
            print(f"   {uid}: {len(entries)} entries")
            for e in entries:
                entry = e.get("entry", {})
                print(f"     - {e['session_date']} | {entry.get('spot_name', '?')} | "
                      f"{entry.get('discipline', '?')}")
        else:
            print(f"   {uid}: 0 entries")

    # 4. Check __legacy__ user state for outdoor_log summary
    print("\n4. Checking __legacy__ user_state.outdoor_log[]...")
    legacy_state_r = sb.table("users").select("state").eq("user_id", "__legacy__").execute()
    if legacy_state_r.data:
        state = legacy_state_r.data[0].get("state", {})
        ol = state.get("outdoor_log", [])
        if ol:
            print(f"   Found {len(ol)} summary entries in state.outdoor_log:")
            for entry in ol:
                print(f"   - {entry.get('date', '?')} | {entry.get('spot_name', '?')} | "
                      f"load: {entry.get('load_score', '?')}")
        else:
            print("   No outdoor_log entries in __legacy__ state.")
    else:
        print("   No __legacy__ user state found.")

    # 5. Check each real user's state.outdoor_log for cross-reference
    print("\n5. Cross-reference: user_state.outdoor_log[] per user:")
    for u in users:
        uid = u["user_id"]
        state_r = sb.table("users").select("state").eq("user_id", uid).execute()
        if state_r.data:
            state = state_r.data[0].get("state", {})
            ol = state.get("outdoor_log", [])
            if ol:
                print(f"   {uid}: {len(ol)} summary entries")
                for entry in ol:
                    print(f"     - {entry.get('date', '?')} | {entry.get('spot_name', '?')} | "
                          f"load: {entry.get('load_score', '?')}")
            else:
                print(f"   {uid}: 0 summary entries")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Legacy outdoor_logs entries: {len(legacy_entries)}")
    print(f"Known users: {len(users)}")
    if legacy_entries and users:
        print(f"\nProposed action: reassign {len(legacy_entries)} entries to a target user.")
        if len(users) == 1:
            print(f"Only one user found: {users[0]['user_id']} — likely the owner.")
        else:
            print("Multiple users found — specify --target-user to choose.")

    # Apply if requested
    if args.apply:
        if not legacy_entries:
            print("\nNothing to reassign.")
            return
        if not args.target_user:
            if len(users) == 1:
                args.target_user = users[0]["user_id"]
                print(f"\nAuto-selected target user: {args.target_user}")
            else:
                print("\nERROR: --target-user is required when multiple users exist.")
                sys.exit(1)

        print(f"\nReassigning {len(legacy_entries)} entries to user {args.target_user}...")
        for entry in legacy_entries:
            sb.table("outdoor_logs").update({"user_id": args.target_user}).eq(
                "id", entry["id"]
            ).execute()
            print(f"  ✓ {entry['session_date']}")
        print("Done. Verify with GET /api/outdoor/sessions.")
    else:
        if legacy_entries:
            print("\nRun with --apply to reassign data. NO changes were made.")


if __name__ == "__main__":
    main()
