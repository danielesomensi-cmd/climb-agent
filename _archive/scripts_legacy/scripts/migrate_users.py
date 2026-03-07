#!/usr/bin/env python3
"""Migrate all user data from old backend to new backend.

Usage:
    export ADMIN_SECRET="your-admin-key"
    python scripts/migrate_users.py

Old backend: https://climb-agent-production.up.railway.app
New backend: https://web-production-fb1e9.up.railway.app
"""

import json
import os
import sys
import time

import requests

OLD_BACKEND = "https://climb-agent-production.up.railway.app"
NEW_BACKEND = "https://web-production-fb1e9.up.railway.app"

OLD_ADMIN_SECRET = os.environ.get("OLD_ADMIN_SECRET", "")
NEW_ADMIN_SECRET = os.environ.get("NEW_ADMIN_SECRET", "")

if not OLD_ADMIN_SECRET or not NEW_ADMIN_SECRET:
    print("ERROR: set both OLD_ADMIN_SECRET and NEW_ADMIN_SECRET env vars")
    print("  export OLD_ADMIN_SECRET='temp key set on old Railway project'")
    print("  export NEW_ADMIN_SECRET='key from new Railway project'")
    sys.exit(1)


def _admin_key(base_url: str) -> str:
    return OLD_ADMIN_SECRET if base_url == OLD_BACKEND else NEW_ADMIN_SECRET


def list_users(base_url: str) -> list[dict]:
    """GET /api/admin/users from a backend."""
    r = requests.get(
        f"{base_url}/api/admin/users",
        headers={"X-Admin-Key": _admin_key(base_url)},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    return data["users"]


def export_state(base_url: str, uuid: str) -> dict:
    """GET /api/user/export for a specific user."""
    r = requests.get(
        f"{base_url}/api/user/export",
        headers={"X-User-ID": uuid},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def import_state(base_url: str, uuid: str, state: dict) -> None:
    """POST /api/user/import for a specific user."""
    r = requests.post(
        f"{base_url}/api/user/import",
        headers={"X-User-ID": uuid, "Content-Type": "application/json"},
        json=state,
        timeout=30,
    )
    r.raise_for_status()


def verify_state(base_url: str, uuid: str, original: dict) -> bool:
    """Export from new backend and compare with original."""
    exported = export_state(base_url, uuid)
    # Compare key fields (import may add metadata, so check essential keys)
    for key in ("schema_version", "goal", "assessment", "macrocycle"):
        if exported.get(key) != original.get(key):
            return False
    return True


def main():
    print(f"=== Migration: {OLD_BACKEND} -> {NEW_BACKEND} ===\n")

    # Step 1: List users on old backend
    print("1. Listing users on OLD backend...")
    old_users = list_users(OLD_BACKEND)
    print(f"   Found {len(old_users)} users\n")

    # Step 2: Check new backend status
    print("2. Checking NEW backend...")
    try:
        new_users = list_users(NEW_BACKEND)
        print(f"   New backend has {len(new_users)} existing users\n")
    except Exception as e:
        print(f"   Warning: could not list new backend users: {e}\n")

    # Step 3: Migrate each user
    migrated = []
    failed = []
    skipped = []

    # Collect existing UUIDs on new backend to avoid overwriting
    new_uuids = {u["uuid"] for u in new_users} if new_users else set()

    for i, user in enumerate(old_users, 1):
        uuid = user["uuid"]
        grade = user.get("grade", "?")
        sessions = user.get("sessions_completed", 0)

        print(f"3.{i:02d} [{uuid[:8]}...] grade={grade}, sessions={sessions}")

        if uuid in new_uuids:
            print(f"     SKIP: already exists on new backend")
            skipped.append(uuid)
            continue

        try:
            # Export from old
            state = export_state(OLD_BACKEND, uuid)
            print(f"     Exported ({len(json.dumps(state))} bytes)")

            # Import to new
            import_state(NEW_BACKEND, uuid, state)
            print(f"     Imported")

            # Verify
            if verify_state(NEW_BACKEND, uuid, state):
                print(f"     Verified OK")
                migrated.append(uuid)
            else:
                print(f"     WARNING: verification mismatch!")
                failed.append(uuid)

            time.sleep(0.3)  # be gentle with the server

        except Exception as e:
            print(f"     FAILED: {e}")
            failed.append(uuid)

    # Summary
    print(f"\n=== Summary ===")
    print(f"Total users on old backend: {len(old_users)}")
    print(f"Migrated successfully:      {len(migrated)}")
    print(f"Skipped (already exist):    {len(skipped)}")
    print(f"Failed:                     {len(failed)}")

    if failed:
        print(f"\nFailed UUIDs:")
        for uuid in failed:
            print(f"  - {uuid}")
        sys.exit(1)

    # Final verification: count users on new backend
    print(f"\n4. Final check on NEW backend...")
    final_users = list_users(NEW_BACKEND)
    print(f"   New backend now has {len(final_users)} users")
    print(f"\nMigration complete. Do NOT delete old backend until you've confirmed everything works.")


if __name__ == "__main__":
    main()
