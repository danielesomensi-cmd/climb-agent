"""
A121 — Sort Category Derivation Audit

Audit-only script: loads ALL exercises and tests the draft infer_sort_category()
mapping function. Does NOT modify any existing code.
"""

import json
import os
from collections import defaultdict
from typing import Any, Dict, List

import pytest

EXERCISES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "backend", "catalog", "exercises", "v1", "exercises.json"
)
# Normalize
EXERCISES_PATH = os.path.normpath(EXERCISES_PATH)

SORT_CATEGORIES = [
    "warmup",
    "activation",
    "aerobic_pure",
    "threshold",
    "strength_neural",
    "power",
    "pe_intervals",
    "finger_endurance",
    "pulling_supplementary",
    "core",
    "antagonist_prehab",
    "cooldown",
    "technique",
    "main_unclassified",
]


def infer_sort_category(exercise: dict) -> str:
    """
    Derive sort category from existing exercise fields.
    Returns one of the 12+1 sort categories or 'main_unclassified'.
    """
    role = exercise.get("role", "")
    roles = role if isinstance(role, list) else [role]
    roles = [str(r).strip().lower() for r in roles if r]
    domain_raw = exercise.get("domain", "")
    domains = domain_raw if isinstance(domain_raw, list) else [domain_raw]
    domains = [str(d).strip().lower() for d in domains if d]
    domain = domains[0] if domains else ""
    pattern_raw = exercise.get("pattern", "")
    patterns = pattern_raw if isinstance(pattern_raw, list) else [pattern_raw]
    patterns = [str(p).strip().lower() for p in patterns if p]
    pattern = patterns[0] if patterns else ""

    # --- Priority 1: role-based (unambiguous) ---
    if "warmup" in roles and "main" not in roles:
        return "warmup"
    if "cooldown" in roles:
        return "cooldown"
    if "activation" in roles and "main" not in roles:
        return "activation"

    # --- Priority 2: domain-based ---
    # Aerobic pure
    if domain in ("aerobic_capacity", "regeneration"):
        return "aerobic_pure"
    if domain == "finger_aerobic_endurance":
        return "aerobic_pure"

    # Strength neural
    if domain == "finger_max_strength":
        return "strength_neural"
    if domain == "contact_strength":
        return "strength_neural"

    # Power
    if domain == "power":
        return "power"

    # PE intervals
    if domain == "power_endurance":
        return "pe_intervals"
    if domain == "anaerobic_capacity":
        return "pe_intervals"

    # Finger endurance
    if domain == "finger_strength_endurance":
        return "finger_endurance"
    if domain == "finger_strength" and pattern == "repeater_hang":
        return "finger_endurance"
    # finger_strength with isometric_hang → strength_neural
    if domain == "finger_strength" and pattern == "isometric_hang":
        return "strength_neural"
    # finger_strength fallback (legacy umbrella)
    if domain == "finger_strength":
        return "finger_endurance"

    # Lock-off endurance (not in original draft — discovered during audit)
    if domain == "lock_off_endurance":
        return "pulling_supplementary"

    # Threshold / climbing volume
    if domain == "endurance":
        return "threshold"
    if domain == "climbing_routes":
        return "threshold"

    # Core
    if domain == "core":
        return "core"

    # Antagonist / prehab
    if domain in ("prehab_elbow", "prehab_finger", "prehab_shoulder", "prehab_wrist"):
        return "antagonist_prehab"

    # Strength general / pulling
    if domain == "strength_general":
        if pattern in ("pull_vertical", "pull_horizontal"):
            return "pulling_supplementary"
        return "antagonist_prehab"
    if domain == "strength_pulling":
        return "pulling_supplementary"

    # Mobility / flexibility
    if domain in ("mobility", "flexibility"):
        return "cooldown"

    # Technique
    if domain.startswith("technique_"):
        return "technique"
    if "technique" in roles:
        return "technique"

    # Handstand
    if domain == "handstand_skill":
        return "core"  # treat as core-adjacent

    # Recovery role fallback
    if "recovery" in roles:
        return "cooldown"

    # Test role fallback — tests are typically strength or endurance tests
    if "test" in roles:
        return "strength_neural"

    # FALLBACK — never lose the exercise
    return "main_unclassified"


def load_exercises() -> List[Dict[str, Any]]:
    with open(EXERCISES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "exercises" in data:
        return data["exercises"]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unexpected format in {EXERCISES_PATH}")


def test_a121_sort_category_audit():
    """Full audit: derive sort_category for every exercise, print report."""
    exercises = load_exercises()
    assert len(exercises) > 0, "Exercise catalog is empty"

    by_category: Dict[str, List[dict]] = defaultdict(list)
    unclassified: List[dict] = []
    ambiguous: List[dict] = []

    for ex in exercises:
        ex_id = ex.get("id") or ex.get("exercise_id") or "unknown"
        cat = infer_sort_category(ex)
        by_category[cat].append(ex)

        if cat == "main_unclassified":
            unclassified.append(ex)

        # Flag ambiguous cases
        role = ex.get("role", "")
        roles = role if isinstance(role, list) else [role]
        roles = [str(r).strip().lower() for r in roles if r]
        domain_raw = ex.get("domain", "")
        domains = domain_raw if isinstance(domain_raw, list) else [domain_raw]
        domains = [str(d).strip().lower() for d in domains if d]

        # Multi-role with warmup + something else
        if "warmup" in roles and len(roles) > 1:
            ambiguous.append({
                "exercise_id": ex_id,
                "reason": f"multi-role with warmup: {roles}",
                "assigned": cat,
                "domain": domains,
            })
        # strength_general disambiguation
        if "strength_general" in domains:
            ambiguous.append({
                "exercise_id": ex_id,
                "reason": f"strength_general — pulling vs antagonist?",
                "assigned": cat,
                "pattern": ex.get("pattern"),
            })
        # finger_strength legacy
        if "finger_strength" in domains and "warmup" not in roles:
            ambiguous.append({
                "exercise_id": ex_id,
                "reason": f"finger_strength (legacy umbrella)",
                "assigned": cat,
                "pattern": ex.get("pattern"),
            })

    # ========== REPORT ==========
    total = len(exercises)
    mapped = total - len(unclassified)
    mapped_pct = 100.0 * mapped / total if total else 0
    unclass_pct = 100.0 * len(unclassified) / total if total else 0

    print("\n" + "=" * 60)
    print("=== A121 SORT CATEGORY AUDIT ===")
    print("=" * 60)

    print(f"\nCOVERAGE SUMMARY:")
    print(f"  Total exercises: {total}")
    print(f"  Mapped successfully: {mapped} ({mapped_pct:.1f}%)")
    print(f"  Fallback (main_unclassified): {len(unclassified)} ({unclass_pct:.1f}%)")

    print(f"\nBY CATEGORY:")
    for cat in SORT_CATEGORIES:
        count = len(by_category.get(cat, []))
        marker = " ← REVIEW THESE" if cat == "main_unclassified" and count > 0 else ""
        print(f"  {cat}: {count} exercises{marker}")

    if unclassified:
        print(f"\nUNCLASSIFIED EXERCISES (need manual review):")
        for ex in unclassified:
            ex_id = ex.get("id") or ex.get("exercise_id") or "unknown"
            role = ex.get("role", "")
            domain = ex.get("domain", "")
            pattern = ex.get("pattern", "")
            print(f"  - {ex_id} | role: {role} | domain: {domain} | pattern: {pattern}")
    else:
        print(f"\nUNCLASSIFIED EXERCISES: None — 100% coverage!")

    if ambiguous:
        print(f"\nPOTENTIAL AMBIGUITIES ({len(ambiguous)} flagged):")
        for a in ambiguous:
            print(f"  - {a['exercise_id']}: {a['reason']} → assigned: {a['assigned']}")

    print(f"\nEXERCISES PER CATEGORY (full list):")
    for cat in SORT_CATEGORIES:
        exs = by_category.get(cat, [])
        if not exs:
            continue
        print(f"\n  [{cat}] ({len(exs)} exercises)")
        for ex in sorted(exs, key=lambda e: e.get("id", "")):
            ex_id = ex.get("id") or ex.get("exercise_id") or "unknown"
            role = ex.get("role", "")
            domain = ex.get("domain", "")
            print(f"    - {ex_id} (role={role}, domain={domain})")

    print("\n" + "=" * 60)

    # ========== ASSERTIONS ==========
    # The mapping must cover all exercises (no crashes)
    assert total == mapped + len(unclassified)

    # P0 invariant: no exercises lost — set before == set after
    ids_before = set(ex.get("id") or ex.get("exercise_id") for ex in exercises)
    ids_after = set()
    for cat_exs in by_category.values():
        for ex in cat_exs:
            ids_after.add(ex.get("id") or ex.get("exercise_id"))
    assert ids_before == ids_after, "EXERCISE LOSS DETECTED — sort categories lost exercises!"

    # Soft target: unclassified should be < 5%
    if unclass_pct > 5.0:
        print(f"\n⚠ WARNING: {unclass_pct:.1f}% unclassified — mapping needs refinement")


def test_a121_sort_is_pure_reorder():
    """Verify that sorting by infer_sort_category is a pure reorder — no exercises lost."""
    exercises = load_exercises()
    ids_before = [ex.get("id") or ex.get("exercise_id") for ex in exercises]

    sorted_exercises = sorted(exercises, key=lambda ex: infer_sort_category(ex))
    ids_after = [ex.get("id") or ex.get("exercise_id") for ex in sorted_exercises]

    assert set(ids_before) == set(ids_after), "Sorting lost exercises!"
    assert len(ids_before) == len(ids_after), "Sorting changed exercise count!"


def test_a121_no_crash_on_edge_cases():
    """Mapping function must not crash on minimal/empty exercise dicts."""
    edge_cases = [
        {},
        {"id": "empty"},
        {"role": "main"},
        {"role": ["warmup", "main"]},
        {"domain": "unknown_domain_xyz"},
        {"domain": ["finger_strength", "core"]},
        {"role": "warmup", "domain": "finger_strength", "pattern": "isometric_hang"},
    ]
    for ex in edge_cases:
        cat = infer_sort_category(ex)
        assert cat in SORT_CATEGORIES, f"Unknown category '{cat}' for exercise {ex}"
