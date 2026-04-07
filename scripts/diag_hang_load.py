import json, sys, os
sys.path.insert(0, os.getcwd())

from backend.engine.progression_v1 import inject_targets, HANGBOARD_DEFAULT_INTENSITY_PCT

USER_ID = "7ea9f0ee-e629-4ce9-8f4f-f8e6e3dc771e"

# 1. Load user state
state = json.load(open(f"data/users/{USER_ID}/user_state.json"))
assert state.get("profile", {}).get("name", "").lower() == "daniele", "Wrong user!"

# 2. Print key fields
print("=== PROFILE ===")
print(f"  bodyweight_kg: {state.get('profile', {}).get('bodyweight_kg', 'MISSING')}")

print("\n=== BASELINES.HANGBOARD ===")
hb = state.get("baselines", {}).get("hangboard", [])
if not hb:
    print("  EMPTY - no hangboard baseline found!")
else:
    for entry in hb:
        print(f"  {json.dumps(entry, indent=4)}")

print("\n=== WORKING_LOADS for max_hang_7s ===")
wl = state.get("working_loads", {}).get("entries", [])
hang_entries = [e for e in wl if "max_hang_7s" in e.get("exercise_id", "") or "max_hang_7s" in e.get("key", "")]
if not hang_entries:
    print("  No working_loads entry for max_hang_7s")
else:
    for entry in hang_entries:
        print(f"  {json.dumps(entry, indent=4)}")

print("\n=== ADJUSTMENTS (closed-loop multiplier) ===")
adj = state.get("adjustments", {}).get("per_exercise", {})
for key in sorted(adj.keys()):
    if "hang" in key.lower():
        print(f"  {key}: {json.dumps(adj[key])}")
if not any("hang" in k.lower() for k in adj):
    print("  No hangboard multipliers found")

print("\n=== HANGBOARD_DEFAULT_INTENSITY_PCT ===")
for ex_id, pct in sorted(HANGBOARD_DEFAULT_INTENSITY_PCT.items()):
    if "7s" in ex_id or "7_53" in ex_id:
        print(f"  {ex_id}: {pct}")

print("\n=== MANUAL CALCULATION ===")
if hb:
    baseline = hb[0]
    max_total = baseline.get("max_total_load_kg", 0)
    bw = state.get("profile", {}).get("bodyweight_kg", 0)
    intensity = 0.90

    mult_entry = adj.get("max_hang_7s", {})
    multiplier = mult_entry.get("multiplier", 1.0)

    target = max_total * intensity * multiplier
    added = target - bw

    print(f"  max_total_load_kg = {max_total}")
    print(f"  bodyweight_kg = {bw}")
    print(f"  intensity_pct = {intensity}")
    print(f"  multiplier = {multiplier}")
    print(f"  target_total = {max_total} x {intensity} x {multiplier} = {target:.1f} kg")
    print(f"  added_weight = {target:.1f} - {bw} = {added:.1f} kg")
    print(f"  (UI shows: +{round(added)} kg, total {round(target)} kg)")

    print(f"\n  Baseline hang_seconds: {baseline.get('hang_seconds', 'MISSING')}")
    print(f"  Baseline edge_mm: {baseline.get('edge_mm', 'MISSING')}")
    print(f"  Baseline grip: {baseline.get('grip', 'MISSING')}")
    print(f"  Baseline updated_at: {baseline.get('updated_at', 'MISSING')}")
