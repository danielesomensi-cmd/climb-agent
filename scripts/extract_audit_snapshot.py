#!/usr/bin/env python3
"""Extract a comprehensive audit snapshot of the climb-agent engine.

Generates a single markdown file with 12 sections covering macrocycle structure,
planner logic, catalogs, resolver pipeline, progression, safety gates, user state,
process cues, load model, and identified gaps.

Usage:
    python scripts/extract_audit_snapshot.py
    python scripts/extract_audit_snapshot.py --output docs/audit_snapshot_2026-03-26.md
    python scripts/extract_audit_snapshot.py --user-id 7ea9f0ee-e629-4ce9-8f4f-f8e6e3dc771e
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(rel_path: str) -> Any:
    p = REPO_ROOT / rel_path
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _read_file(rel_path: str) -> str:
    p = REPO_ROOT / rel_path
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def _extract_dict_literal(source: str, var_name: str) -> Optional[str]:
    """Extract a top-level dict assignment from Python source (best-effort)."""
    pattern = rf"^{var_name}\s*[=:]\s*\{{" if ":" not in var_name else rf'"{var_name}":\s*\{{'
    for i, line in enumerate(source.splitlines()):
        if re.search(pattern, line):
            # Grab from this line until brace-balanced
            start = i
            depth = 0
            for j, ch in enumerate(source.splitlines()[i:]):
                depth += ch.count("{") - ch.count("}")
                if depth == 0:
                    return "\n".join(source.splitlines()[start : start + j + 1])
            break
    return None


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def section_macrocycle() -> str:
    src = _read_file("backend/engine/macrocycle_v1.py")
    lines = src.splitlines()

    out = ["# Section 1: MACROCYCLE STRUCTURE\n"]

    # --- Phase order & names ---
    out.append("## Phase Definitions\n")
    out.append("```")
    out.append('PHASE_ORDER = ("base", "strength_power", "power_endurance", "performance", "deload")')
    out.append("```\n")

    out.append("| Phase | Display Name | Energy System | Intensity Cap |")
    out.append("|-------|-------------|---------------|---------------|")
    phase_meta = {
        "base": ("Endurance Base", "aerobic", "medium"),
        "strength_power": ("Strength & Power", "anaerobic_alactic", "max"),
        "power_endurance": ("Power Endurance", "anaerobic_lactic", "high"),
        "performance": ("Performance", "specific", "max"),
        "deload": ("Deload", "recovery", "low"),
    }
    for p, (name, energy, cap) in phase_meta.items():
        out.append(f"| {p} | {name} | {energy} | {cap} |")
    out.append("")

    # --- Base durations ---
    out.append("## Base Durations (weeks)\n")
    out.append("| Phase | Lead | Boulder |")
    out.append("|-------|------|---------|")
    lead_dur = {"base": 4, "strength_power": 3, "power_endurance": 2, "performance": 2, "deload": 1}
    boulder_dur = {"base": 2, "strength_power": 4, "power_endurance": 1, "performance": 2, "deload": 1}
    for p in lead_dur:
        out.append(f"| {p} | {lead_dur[p]} | {boulder_dur[p]} |")
    out.append(f"\n_MIN_TOTAL_WEEKS = 9\n")

    # --- Floor logic ---
    out.append("## Phase Floor Logic\n")
    out.append("- Lead: floor = 2 weeks per non-deload phase; deload = 1 week")
    out.append("- Boulder: floor = 1 week per non-deload phase; deload = 1 week")
    out.append("- Weakness adjustments: if weakest axis score < 50, extend relevant phase +1wk, shrink paired phase -1wk")
    out.append("")

    out.append("### Weakness Adjustments\n")
    out.append("| Weak Axis | Extend Phase | Shrink Phase |")
    out.append("|-----------|-------------|-------------|")
    weakness = {
        "power_endurance": ("power_endurance", "strength_power"),
        "endurance": ("base", "strength_power"),
        "finger_strength": ("strength_power", "base"),
        "pulling_strength": ("strength_power", "base"),
        "technique": ("base", "performance"),
    }
    for axis, (ext, shr) in weakness.items():
        out.append(f"| {axis} | {ext} | {shr} |")
    out.append("")

    # --- Domain weight tables ---
    out.append("## Domain Weight Tables\n")
    out.append("### Lead Discipline\n")
    lead_weights = {
        "base": {"finger_strength": 0.20, "pulling_strength": 0.15, "power_endurance": 0.15, "volume_climbing": 0.25, "technique": 0.20, "core_prehab": 0.05},
        "strength_power": {"finger_strength": 0.35, "pulling_strength": 0.25, "power_endurance": 0.10, "volume_climbing": 0.10, "technique": 0.10, "core_prehab": 0.10},
        "power_endurance": {"finger_strength": 0.15, "pulling_strength": 0.10, "power_endurance": 0.35, "volume_climbing": 0.15, "technique": 0.15, "core_prehab": 0.10},
        "performance": {"finger_strength": 0.10, "pulling_strength": 0.05, "power_endurance": 0.20, "volume_climbing": 0.25, "technique": 0.25, "core_prehab": 0.15},
        "deload": {"finger_strength": 0.05, "pulling_strength": 0.05, "power_endurance": 0.05, "volume_climbing": 0.10, "technique": 0.05, "core_prehab": 0.10},
    }
    domains = ["finger_strength", "pulling_strength", "power_endurance", "volume_climbing", "technique", "core_prehab"]
    out.append("| Phase | " + " | ".join(domains) + " |")
    out.append("|-------|" + "|".join(["-----"] * len(domains)) + "|")
    for phase, weights in lead_weights.items():
        vals = " | ".join(str(weights[d]) for d in domains)
        out.append(f"| {phase} | {vals} |")
    out.append("")

    out.append("### Boulder Discipline\n")
    boulder_weights = {
        "base": {"finger_strength": 0.20, "pulling_strength": 0.15, "power_endurance": 0.05, "volume_climbing": 0.35, "technique": 0.20, "core_prehab": 0.05},
        "strength_power": {"finger_strength": 0.40, "pulling_strength": 0.25, "power_endurance": 0.10, "volume_climbing": 0.10, "technique": 0.10, "core_prehab": 0.05},
        "power_endurance": {"finger_strength": 0.20, "pulling_strength": 0.15, "power_endurance": 0.30, "volume_climbing": 0.20, "technique": 0.10, "core_prehab": 0.05},
        "performance": {"finger_strength": 0.15, "pulling_strength": 0.10, "power_endurance": 0.15, "volume_climbing": 0.30, "technique": 0.25, "core_prehab": 0.05},
        "deload": {"finger_strength": 0.05, "pulling_strength": 0.05, "power_endurance": 0.05, "volume_climbing": 0.10, "technique": 0.05, "core_prehab": 0.10},
    }
    out.append("| Phase | " + " | ".join(domains) + " |")
    out.append("|-------|" + "|".join(["-----"] * len(domains)) + "|")
    for phase, weights in boulder_weights.items():
        vals = " | ".join(str(weights[d]) for d in domains)
        out.append(f"| {phase} | {vals} |")
    out.append("")

    # --- Domain weight adjustment ---
    out.append("## Domain Weight Adjustment (per user profile)\n")
    out.append("- Score < 50 on axis → +0.05 to mapped weight domain")
    out.append("- Score > 75 on axis → -0.03 from mapped weight domain (min 0.02)")
    out.append("- Renormalize to sum = 1.0")
    out.append("- Axis → domain: finger_strength→finger_strength, pulling_strength→pulling_strength, power_endurance→power_endurance, technique→technique, endurance→volume_climbing")
    out.append("")

    # --- Session pools ---
    out.append("## Session Pools per Phase\n")
    pools = {
        "lead": {
            "base": {
                "primary": ["boulder_circuit_gym", "endurance_aerobic_gym", "finger_maintenance_home", "finger_maintenance_gym", "prehab_maintenance", "technique_focus_gym"],
                "available": ["complementary_conditioning", "flexibility_full", "finger_aerobic_base", "finger_endurance_short", "handstand_practice", "route_endurance_gym"],
            },
            "strength_power": {
                "primary": ["finger_strength_home", "limit_boulder_gym", "power_contact_gym", "prehab_maintenance", "strength_long"],
                "available": ["complementary_conditioning", "finger_endurance_short", "finger_maintenance_gym", "flexibility_full", "handstand_practice", "technique_focus_gym"],
            },
            "power_endurance": {
                "primary": ["power_endurance_gym", "prehab_maintenance"],
                "available": ["endurance_aerobic_gym", "flexibility_full", "finger_strength_home", "handstand_practice", "route_endurance_gym", "technique_focus_gym"],
            },
            "performance": {
                "primary": ["limit_boulder_gym", "prehab_maintenance", "technique_focus_gym"],
                "available": ["boulder_circuit_gym", "finger_strength_home", "flexibility_full", "handstand_practice", "power_contact_gym", "power_endurance_gym", "route_endurance_gym"],
            },
            "deload": {
                "primary": ["flexibility_full", "prehab_maintenance", "regeneration_easy", "yoga_recovery"],
                "available": ["deload_recovery", "easy_climbing_deload", "finger_aerobic_base"],
            },
        },
        "boulder": {
            "base": {
                "primary": ["boulder_circuit_gym", "technique_focus_gym", "finger_maintenance_home", "prehab_maintenance"],
                "available": ["flexibility_full", "handstand_practice", "complementary_conditioning", "core_training"],
            },
            "strength_power": {
                "primary": ["power_contact_gym", "limit_boulder_gym", "strength_long", "finger_strength_home", "prehab_maintenance"],
                "available": ["technique_focus_gym", "flexibility_full", "handstand_practice", "complementary_conditioning", "core_training"],
            },
            "power_endurance": {
                "primary": ["boulder_circuit_gym", "prehab_maintenance"],
                "available": ["technique_focus_gym", "finger_strength_home", "flexibility_full", "core_training"],
            },
            "performance": {
                "primary": ["technique_focus_gym", "limit_boulder_gym", "prehab_maintenance"],
                "available": ["power_contact_gym", "boulder_circuit_gym", "finger_strength_home", "flexibility_full", "handstand_practice", "core_training"],
            },
            "deload": {
                "primary": ["regeneration_easy", "flexibility_full", "yoga_recovery", "prehab_maintenance"],
                "available": ["easy_climbing_deload", "deload_recovery", "finger_aerobic_base"],
            },
        },
    }
    for disc, phases in pools.items():
        out.append(f"### {disc.title()} Discipline\n")
        for phase, data in phases.items():
            out.append(f"**{phase}:**")
            out.append(f"- Primary: {', '.join(data['primary'])}")
            out.append(f"- Available: {', '.join(data['available'])}")
            out.append("")

    # --- Deload structure ---
    out.append("## Deload Structure\n")
    out.append("- Deload session pool: regeneration_easy, flexibility_full, yoga_recovery, prehab_maintenance, easy_climbing_deload")
    out.append("- Hard cap during deload: 0 hard days, 0 finger days")
    out.append("- Deload factor: 0.5")
    out.append("- Max sessions/week during deload: 5")
    out.append("")

    # --- Phase transition ---
    out.append("## Phase Transition Logic\n")
    out.append("- Each phase has explicit start_week and end_week bounds")
    out.append("- Week counter increments per phase duration")
    out.append("- `should_extend_phase()`: if last 2 weeks feedback = hard/very_hard → extend +1wk (max +2)")
    out.append("- `should_trigger_adaptive_deload()`: if 5+ consecutive very_hard days → trigger recovery deload")
    out.append("- Pre-trip deload: 5 days before trip, no hard/max sessions")
    out.append("")

    # --- DUP ---
    out.append("## DUP Implementation\n")
    out.append("- Domain weights per phase encode the undulating emphasis")
    out.append("- Session pools rotate cyclically (primary_idx % len(pool)) for week-to-week variety")
    out.append("- Max per week limits (default 1) prevent session repetition within a week")
    out.append("- Recovery multiplier (D83) extends spacing between hard/finger days")
    out.append("- `generate_macrocycle()` supports `from_phase` for partial regeneration")
    out.append("")

    return "\n".join(out)


def section_planner() -> str:
    out = ["# Section 2: PLANNER LOGIC (planner_v2.py)\n"]

    out.append("## 3-Pass Algorithm Overview\n")
    out.append("```")
    out.append("PASS 1:   Place primary sessions (hard=True OR climbing=True)")
    out.append("          → gym-first day order, respects all constraints")
    out.append("PASS 1.5: Climbing fallback for empty gym days")
    out.append("          → technique_focus_gym / easy_climbing_deload if pool lacks gym_boulder")
    out.append("PASS 2:   Fill remaining empty days with complementary sessions")
    out.append("          → up to target_training_days_per_week")
    out.append("PASS 2.2: Fill extra slots on multi-slot days (non-hard only)")
    out.append("          → B121: if total < session_target, add to existing session days")
    out.append("PASS 2.5: Ensure PE phase has finger maintenance")
    out.append("          → finger_maintenance_home/gym if none placed")
    out.append("PASS 3:   Inject test sessions (last week of base/strength_power)")
    out.append("          → replace complementary sessions, respect finger/hard spacing")
    out.append("```\n")

    # --- Constraints ---
    out.append("## Constraint System\n")
    out.append("### PERMANENT constraints (burn uses if hit, session skipped permanently):")
    out.append("- Anti-repetition: session_count >= max_per_week")
    out.append("- Hard day cap: hard_days >= effective_hard_cap\n")
    out.append("### TEMPORARY constraints (defer, don't burn uses):")
    out.append("- Finger gap: meta.finger AND offset - last_finger_offset <= finger_gap_days")
    out.append("- Hard gap: meta.hard AND offset - last_hard_offset <= hard_gap_days")
    out.append("- Other-activity reduction: day has other_activity AND meta.hard")
    out.append("- Pre-trip deload: date in pretrip_set AND (meta.hard OR intensity=max)")
    out.append("- Preferred equipment deferral: B160d, defer to later day with better gear\n")

    # --- Day assignment ---
    out.append("## Day Assignment Logic\n")
    out.append("1. Score each day: gym_preferred=+100, gym_available=+50, home=+1, evening_slot=+10")
    out.append("2. Sort by (-score, offset) → gym days first, stable weekday order within group")
    out.append("3. Youth cap (D81): if age < 18 → max 4 days/week")
    out.append("4. If available_days > target_days → keep only top-scoring days\n")

    # --- Slot selection ---
    out.append("## Slot Selection\n")
    out.append("- Primary sessions prefer: evening > morning > lunch")
    out.append("- Complementary sessions prefer: lunch > morning > evening\n")

    # --- Gym selection ---
    out.append("## Gym Selection\n")
    out.append("1. If slot has specific gym_id → use it")
    out.append("2. If default_gym_id → use it")
    out.append("3. If required_equipment → pick first gym by priority with matching equipment")
    out.append("4. Else → first gym by priority\n")

    # --- Test scheduling ---
    out.append("## Test Scheduling (Pass 3)\n")
    out.append("- Triggers: inject_tests=True OR last week of base/strength_power phase")
    out.append("- TEST_FRESHNESS_DAYS = 42 (6-week minimum between retests)")
    out.append("- Test schedule (ordered):")
    out.append("  1. Finger test: test_lp_max_5s (loading_pin) or test_max_hang_5s (hangboard) — required")
    out.append("  2. Repeater test: test_lp_repeater (loading_pin) or test_repeater_7_3 (hangboard) — required")
    out.append("  3. Pulling test: test_max_weighted_pullup (if baseline or BW pullups ≥15) or test_pullup_bw — optional")
    out.append("- Tests bypass phase intensity cap")
    out.append("- Respect finger/hard spacing, hard cap")
    out.append("- Replace complementary sessions on existing days\n")

    # --- Spacing from prev week ---
    out.append("## Cross-Week Continuity\n")
    out.append("- prev_week_plan seeds hard_day_offsets and finger_day_offsets from last week (offsets -7 to -1)")
    out.append("- Ensures spacing constraints are enforced across week boundaries\n")

    # --- Recovery multiplier ---
    out.append("## Recovery Multiplier (D83)\n")
    out.append("- hard_gap_days = ceil(1 × recovery_multiplier)")
    out.append("- finger_gap_days = ceil(1 × recovery_multiplier)")
    out.append("- Default multiplier = 1.0")
    out.append("- Age 40-49: 1.25, Age 50-59: 1.5, Age 60+: 1.75\n")

    return "\n".join(out)


def section_session_catalog() -> str:
    out = ["# Section 3: SESSION CATALOG\n"]

    sessions_dir = REPO_ROOT / "backend" / "catalog" / "sessions" / "v1"
    sessions = []
    for fp in sorted(sessions_dir.glob("*.json")):
        data = json.loads(fp.read_text(encoding="utf-8"))
        sessions.append(data)

    # --- Session table ---
    out.append(f"Total sessions: {len(sessions)}\n")
    out.append("| session_id | name | location | domains | intensity | climbing | duration_min |")
    out.append("|-----------|------|----------|---------|-----------|----------|-------------|")
    for s in sorted(sessions, key=lambda x: x.get("id", "")):
        sid = s.get("id", "?")
        name = s.get("name", "?")
        loc = s.get("location", "?")
        doms = ", ".join(s.get("domains", []))
        intens = s.get("primary_goal", "?")
        climbing = "Y" if s.get("climbing", False) else "N"
        dur = s.get("duration_minutes", "?")
        out.append(f"| {sid} | {name} | {loc} | {doms} | {intens} | {climbing} | {dur} |")
    out.append("")

    # --- SESSION_META ---
    out.append("## SESSION_META (planner_v2.py)\n")
    meta = {
        "strength_long": {"hard": True, "finger": True, "intensity": "max", "climbing": True, "location": ("gym", "home"), "required_equipment": ["hangboard"]},
        "power_contact_gym": {"hard": True, "finger": False, "intensity": "max", "climbing": True, "location": ("gym",), "required_equipment": ["gym_boulder"]},
        "limit_boulder_gym": {"hard": True, "finger": False, "intensity": "max", "climbing": True, "location": ("gym",), "required_equipment": ["gym_boulder"]},
        "power_endurance_gym": {"hard": True, "finger": False, "intensity": "high", "climbing": True, "location": ("gym",), "required_equipment": ["gym_boulder"], "preferred_equipment": ["gym_routes"]},
        "endurance_aerobic_gym": {"hard": False, "finger": False, "intensity": "medium", "climbing": True, "location": ("gym",), "max_per_week": 2, "required_equipment": ["gym_routes"]},
        "technique_focus_gym": {"hard": False, "finger": False, "intensity": "medium", "climbing": True, "location": ("gym",), "required_equipment": ["gym_boulder"]},
        "finger_strength_home": {"hard": True, "finger": True, "intensity": "high", "climbing": False, "location": ("home",), "required_equipment": ["hangboard"]},
        "prehab_maintenance": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home", "gym")},
        "flexibility_full": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home", "gym"), "max_per_week": 2},
        "yoga_recovery": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home",), "max_per_week": 2},
        "handstand_practice": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("home", "gym")},
        "complementary_conditioning": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("home", "gym")},
        "regeneration_easy": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home", "gym", "outdoor")},
        "finger_maintenance_home": {"hard": False, "finger": True, "intensity": "medium", "climbing": True, "location": ("home",), "required_equipment": ["hangboard"]},
        "test_max_hang_5s": {"hard": True, "finger": True, "intensity": "high", "climbing": False, "location": ("home", "gym"), "test": True, "required_equipment": ["hangboard"]},
        "test_lp_max_5s": {"hard": True, "finger": True, "intensity": "high", "climbing": False, "location": ("home", "gym"), "test": True, "required_equipment": ["loading_pin"]},
        "test_repeater_7_3": {"hard": True, "finger": True, "intensity": "high", "climbing": False, "location": ("home", "gym"), "test": True, "required_equipment": ["hangboard"]},
        "test_lp_repeater": {"hard": True, "finger": True, "intensity": "high", "climbing": False, "location": ("home", "gym"), "test": True, "required_equipment": ["loading_pin"]},
        "test_max_weighted_pullup": {"hard": True, "finger": False, "intensity": "high", "climbing": False, "location": ("home", "gym"), "test": True, "required_equipment": ["pullup_bar"]},
        "test_pullup_bw": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("home", "gym"), "test": True, "required_equipment": ["pullup_bar"]},
        "easy_climbing_deload": {"hard": False, "finger": False, "intensity": "low", "climbing": True, "location": ("gym",), "required_equipment": ["gym_boulder"]},
        "finger_maintenance_gym": {"hard": False, "finger": True, "intensity": "medium", "climbing": True, "location": ("gym",), "required_equipment": ["hangboard"]},
        "route_endurance_gym": {"hard": False, "finger": False, "intensity": "medium", "climbing": True, "location": ("gym",), "required_equipment": ["gym_routes"]},
        "pulling_strength_gym": {"hard": True, "finger": False, "intensity": "high", "climbing": False, "location": ("gym",), "required_equipment": ["pullup_bar"]},
        "heavy_conditioning_gym": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("gym",), "required_equipment": ["dumbbell"]},
        "lower_body_gym": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("gym",), "required_equipment": ["dumbbell"]},
        "finger_aerobic_base": {"hard": False, "finger": True, "intensity": "low", "climbing": False, "location": ("home",), "required_equipment": ["hangboard"]},
        "deload_recovery": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home", "gym"), "max_per_week": 2},
        "finger_endurance_short": {"hard": False, "finger": True, "intensity": "medium", "climbing": False, "location": ("home",), "required_equipment": ["hangboard"]},
        "boulder_circuit_gym": {"hard": False, "finger": False, "intensity": "medium", "climbing": True, "location": ("gym",), "max_per_week": 2, "required_equipment": ["gym_boulder"]},
        "upper_body_weights": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("gym", "home"), "max_per_week": 2},
        "legs_strength": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("gym", "home"), "max_per_week": 2},
        "core_training": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("gym", "home"), "max_per_week": 3},
    }

    out.append("| Session | Hard | Finger | Intensity | Climbing | Location | Equipment | max/wk |")
    out.append("|---------|------|--------|-----------|----------|----------|-----------|--------|")
    for sid, m in sorted(meta.items()):
        hard = "Y" if m.get("hard") else ""
        finger = "Y" if m.get("finger") else ""
        intens = m.get("intensity", "")
        climbing = "Y" if m.get("climbing") else ""
        loc = ", ".join(m.get("location", ()))
        equip = ", ".join(m.get("required_equipment", []))
        pref = m.get("preferred_equipment", [])
        if pref:
            equip += f" (pref: {', '.join(pref)})"
        mpw = m.get("max_per_week", 1)
        out.append(f"| {sid} | {hard} | {finger} | {intens} | {climbing} | {loc} | {equip} | {mpw} |")
    out.append("")

    # --- Always suggestible ---
    out.append("## _ALWAYS_SUGGESTIBLE\n")
    out.append('```python\n_ALWAYS_SUGGESTIBLE = {"core_training"}\n```\n')

    return "\n".join(out)


def section_template_catalog() -> str:
    out = ["# Section 4: TEMPLATE CATALOG\n"]

    tmpl_dir = REPO_ROOT / "backend" / "catalog" / "templates" / "v1"
    templates = []
    for fp in sorted(tmpl_dir.glob("*.json")):
        data = json.loads(fp.read_text(encoding="utf-8"))
        templates.append(data)

    out.append(f"Total templates: {len(templates)}\n")
    for t in sorted(templates, key=lambda x: x.get("id", "")):
        tid = t.get("id", "?")
        name = t.get("name", "?")
        pa = t.get("phase_affinity", [])
        out.append(f"### {tid}")
        out.append(f"**Name:** {name}")
        if pa:
            out.append(f"**Phase affinity:** {', '.join(pa)}")
        out.append("")

        blocks = t.get("blocks", [])
        if blocks:
            out.append("| Block | Roles | Domains | Count |")
            out.append("|-------|-------|---------|-------|")
            for b in blocks:
                bid = b.get("id", "?")
                roles = ", ".join(b.get("roles", []))
                doms = ", ".join(b.get("domains", []))
                count = b.get("pick_count", b.get("count", "?"))
                out.append(f"| {bid} | {roles} | {doms} | {count} |")
            out.append("")

    return "\n".join(out)


def section_exercise_catalog() -> str:
    out = ["# Section 5: EXERCISE CATALOG\n"]

    raw = _load_json("backend/catalog/exercises/v1/exercises.json") or {}
    exercises = raw.get("exercises", raw) if isinstance(raw, dict) else raw
    out.append(f"Total exercises: {len(exercises)}\n")

    # Group by category
    by_cat: Dict[str, List[dict]] = defaultdict(list)
    for e in exercises:
        cat = e.get("category", "uncategorized")
        by_cat[cat].append(e)

    # Counts
    out.append("## Category Counts\n")
    out.append("| Category | Count |")
    out.append("|----------|-------|")
    for cat in sorted(by_cat.keys()):
        out.append(f"| {cat} | {len(by_cat[cat])} |")
    out.append("")

    # Full table per category
    for cat in sorted(by_cat.keys()):
        out.append(f"## {cat} ({len(by_cat[cat])} exercises)\n")
        out.append("| exercise_id | name | domain | intensity | pattern | equipment | phase_affinity | contraindications | recency_group | location | unilateral |")
        out.append("|------------|------|--------|-----------|---------|-----------|---------------|-------------------|---------------|----------|-----------|")
        for e in sorted(by_cat[cat], key=lambda x: x.get("id", "")):
            eid = e.get("id", "?")
            name = e.get("name", "?")
            domain = ", ".join(e.get("domain", [])) if isinstance(e.get("domain"), list) else str(e.get("domain", ""))
            intens = e.get("intensity_level", "")
            pattern = e.get("pattern", "")
            equip = ", ".join(e.get("equipment_required", []) or [])
            pa = ", ".join(e.get("phase_affinity", []) or [])
            contra = ", ".join(e.get("contraindications", []) or [])
            rg = e.get("recency_group", "")
            loc = ", ".join(e.get("location_allowed", []) or [])
            uni = "Y" if e.get("unilateral") else ""
            out.append(f"| {eid} | {name} | {domain} | {intens} | {pattern} | {equip} | {pa} | {contra} | {rg} | {loc} | {uni} |")
        out.append("")

    return "\n".join(out)


def section_resolver() -> str:
    out = ["# Section 6: RESOLVER LOGIC (resolve_session.py)\n"]

    out.append("## P0 Pipeline Stages\n")
    out.append("```")
    out.append("Stage 0:  Start with all exercises in catalog")
    out.append("Stage 1:  Location filter — exercise.location_allowed must include current location")
    out.append("Stage 2:  Equipment hard filter — equipment_required ⊆ available_equipment")
    out.append("          equipment_required_any ∩ available_equipment ≠ ∅")
    out.append("Stage 2b: Block equipment preference (soft — falls back if empty)")
    out.append("Stage 2c: Finger device preference (soft — B126)")
    out.append("          Splits into finger_pool vs other_pool, prefers user's device")
    out.append("Stage 2d: Age gate (D80) — block if exercise.age_minimum > user_age")
    out.append("Stage 2e: Hangboard experience gate (D35)")
    out.append("          Users < 2yr blocked from: max_hang_5s/7s/10s, max_hang_ladder,")
    out.append("          min_edge_hang, one_arm_hang_assisted (exception: role=test)")
    out.append("Stage 2f: Generic experience_minimum_years gate (B159a)")
    out.append("Stage 3:  Role filter — ANY role match required")
    out.append("Stage 3b: Deduplication — exclude recent_ex_ids (soft)")
    out.append("Stage 4:  Domain filter — ANY domain match (soft, skipped if would zero pool)")
    out.append("Stage 5:  Pattern filter — ANY pattern match (soft, skipped if would zero pool)")
    out.append("Stage 6:  Limitation filter")
    out.append("          Severe contraindications → hard block")
    out.append("          Active contraindications → soft block (try to avoid)")
    out.append("```\n")

    out.append("## Exercise Scoring (score_exercise)\n")
    out.append("- Recent exercise_id in last 5 uses: -100")
    out.append("- Recent exercise_id in last 15 uses: -25")
    out.append("- Any recent use: -5")
    out.append("- Recency group penalty (B159b): -15 if rg in recent_recency_groups")
    out.append("- Edge mm preference match: +10")
    out.append("- Grip preference match: +5")
    out.append("- Tie-breaking: sort by (score desc, exercise_id asc)\n")

    out.append("## Load/Prescription Computation\n")
    out.append("- Session load score = round(min(85, raw_fatigue_sum × 1.5))")
    out.append("- Per-exercise: fatigue_cost field summed across all resolved exercises")
    out.append("- Load overrides: user_state.overrides.per_exercise[id] → absolute_load_kg | delta_kg | multiplier\n")

    out.append("## Finger Device Routing\n")
    out.append("- Reads user_state.preferences.finger_training_device")
    out.append("- If not loading_pin: alias loading_pin → hangboard in available_equipment")
    out.append("- Gym location always implies pullup_bar\n")

    out.append("## Exercise Ordering (A121)\n")
    out.append("- Phase-aware ordering: derives effective_phase from macrocycle + current date")
    out.append("- sort_exercises_by_phase() + enforce_ordering_constraints()\n")

    out.append("## Prehab Injection (B38)\n")
    out.append("- For each limitation zone → auto-inject one prehab exercise if not present")
    out.append("- Domain: prehab_{zone}")
    out.append("- If 2+ zones severe → force deload\n")

    out.append("## Contraindication System\n")
    out.append("- Zones: elbow, finger, shoulder, wrist")
    out.append("- Zone → contraindication: elbow→elbow_sensitive, finger→finger_sensitive, etc.")
    out.append("- Severities: monitor (0), active (1), severe (2)")
    out.append("- Legacy migration: mild→monitor, moderate→active, lieve→monitor, moderato→active")
    out.append("- Active limitation: 0.8× load multiplier on prescription\n")

    return "\n".join(out)


def section_progression() -> str:
    out = ["# Section 7: PROGRESSION & ADAPTATION\n"]

    out.append("## Feedback → Load Change (DEFAULT_ADJUSTMENT_POLICY)\n")
    out.append("| Feedback | Adjustment Range | Midpoint |")
    out.append("|----------|-----------------|----------|")
    policy = {
        "very_easy": ("+10%", "+20%", "+15%"),
        "easy": ("+5%", "+10%", "+7.5%"),
        "ok": ("0%", "+5%", "+2.5%"),
        "hard": ("-5%", "0%", "-2.5%"),
        "very_hard": ("-15%", "-5%", "-10%"),
    }
    for fb, (lo, hi, mid) in policy.items():
        out.append(f"| {fb} | [{lo}, {hi}] | {mid} |")
    out.append("")

    out.append("## Grade-Based Feedback (limit bouldering)\n")
    out.append("| Feedback | Grade Delta |")
    out.append("|----------|------------|")
    for fb, delta in [("very_easy", "+2"), ("easy", "+1"), ("ok", "0"), ("hard", "-1"), ("very_hard", "-2")]:
        out.append(f"| {fb} | {delta} |")
    out.append("")

    out.append("## Working Load System\n")
    out.append("- Keyed by: exercise_id + setup (edge_mm/grip/load_method for hangboard, surface for bouldering)")
    out.append("- Fields: last_external_load_kg, next_external_load_kg, last_feedback_label, updated_at")
    out.append("- Fresh within 60 days (preferred); falls back to any fresh entry if setup mismatch")
    out.append("- Formula: next_load = last_load × (1 + midpoint_pct)\n")

    out.append("## Load Transfer (cross-exercise)\n")
    out.append("- Similarity groups: push (bench_press↔dumbbell_bench 0.85), squat (split_squat↔goblet 0.80), pull (barbell_row↔face_pull 0.25)")
    out.append("- Formula: transferred_load = donor_load × (target_coeff / donor_coeff)\n")

    out.append("## Pulling Strength Targets (PULLING_1RM_PCT)\n")
    out.append("| Phase | Easy | Medium | Hard |")
    out.append("|-------|------|--------|------|")
    pulling = {
        "base": ("55%", "65%", "75%"),
        "strength_power": ("65%", "75%", "85%"),
        "power_endurance": ("60%", "70%", "80%"),
        "performance": ("60%", "70%", "85%"),
        "deload": ("40%", "50%", "60%"),
    }
    for phase, (e, m, h) in pulling.items():
        out.append(f"| {phase} | {e} | {m} | {h} |")
    out.append("")

    out.append("## Hangboard Default Intensity\n")
    out.append("| Exercise | % of Max |")
    out.append("|----------|---------|")
    hb = {
        "max_hang_7s": "88%",
        "max_hang_5s": "92%",
        "repeater_15_15": "65%",
        "repeater_7_3": "70%",
        "density_hangs": "55%",
        "min_edge_hang": "100% (bodyweight)",
    }
    for ex, pct in hb.items():
        out.append(f"| {ex} | {pct} |")
    out.append("")

    out.append("## Baseline Sources\n")
    out.append("- Hangboard: baselines.hangboard[0].max_total_load_kg")
    out.append("- Pulling: baselines.pulling.weighted_pullup_1rm_total_kg")
    out.append("- Loading pin: baselines.loading_pin per hand")
    out.append("- Fallback: derive from grade via _FINGER_BENCHMARK (1.10× BW if unknown)")
    out.append("- Brzycki 1RM: weight × 36 / (37 - reps), accurate 1-10 reps\n")

    out.append("## Exercises with Progression Logic\n")
    out.append("- All hangboard exercises (total_load model): max_hang_5s/7s, repeaters, density_hangs")
    out.append("- Weighted pullup (external_load model, uses baselines.pulling)")
    out.append("- Limit bouldering (grade_relative model)")
    out.append("- All external_load exercises: barbell_row, bench_press, split_squat, etc.")
    out.append("- Loading pin exercises (unilateral external_load)\n")

    out.append("## Closed-Loop State Updates\n")
    out.append("- stimulus_recency: {last_done_date, last_skipped_date, done_count, skipped_count} per category")
    out.append("- fatigue_proxy: done_sessions_total, hard_sessions_total, finger_sessions_total, endurance_sessions_total")
    out.append("- Categories: finger_strength, boulder_power, endurance, complementaries\n")

    return "\n".join(out)


def section_safety() -> str:
    out = ["# Section 8: SAFETY GATES & CONSTRAINTS\n"]

    gates = [
        ("Age gate (D80)", "resolve_session.py Stage 2d", "exercise.age_minimum > user_age → blocked. Primary use: campus board exercises (age_minimum=16)."),
        ("Hangboard experience gate (D35)", "resolve_session.py Stage 2e", "Users < 2yr experience blocked from: max_hang_5s/7s/10s, max_hang_ladder, min_edge_hang, one_arm_hang_assisted. Test exercises exempt."),
        ("Generic experience gate (B159a)", "resolve_session.py Stage 2f", "exercise.experience_minimum_years > user.experience → blocked. Campus exercises require 2+ years."),
        ("Contraindication system", "resolve_session.py Stage 6", "Zones: elbow, finger, shoulder, wrist. Severities: monitor/active/severe. Severe=hard block, Active=soft block + 0.8× load."),
        ("RED-S guardrails (D64)", "test_reds_guardrails.py", "Banned weight-loss/body-composition language never appears in codebase. Assessment has exactly 5 axes (no body_composition)."),
        ("Limitation handling", "resolve_session.py normalize_limitations()", "Parse user_state.limitations → {zone: severity}. Auto-inject prehab exercises. Force deload if 2+ severe zones."),
        ("Youth cap (D81)", "planner_v2.py", "Users under 18: max 4 training days per week."),
        ("Recovery multiplier (D83)", "onboarding.py + planner_v2.py", "Age 40-49: 1.25×, 50-59: 1.5×, 60+: 1.75×. Extends hard/finger day spacing."),
        ("Immutability invariant", "replanner_v1.py", "Past sessions with status done/skipped are NEVER modified. Blocks moving, clearing, or overwriting completed sessions."),
        ("Monday-start invariant", "planner_v2.py ensure_monday()", "All start_date must be Monday (weekday 0). Auto-corrects by subtracting days."),
        ("Hard day cap", "planner_v2.py", "Default 3 hard days/week. Deload: 0 hard days. Configurable via planning_prefs.hard_day_cap_per_week."),
        ("Pre-trip deload", "macrocycle_v1.py", "5 days before trip: no hard/max sessions. compute_pretrip_dates() marks affected dates."),
        ("Test freshness", "planner_v2.py", "42-day minimum between retests of same type (finger/repeater/pulling)."),
    ]

    out.append("| Gate | Location | Description |")
    out.append("|------|----------|-------------|")
    for name, loc, desc in gates:
        out.append(f"| {name} | {loc} | {desc} |")
    out.append("")

    return "\n".join(out)


def section_user_state(user_id: str) -> str:
    out = ["# Section 9: USER STATE\n"]

    # Try local user state files
    users_dir = REPO_ROOT / "backend" / "data" / "users"
    found = False

    if users_dir.exists():
        for uid_dir in users_dir.iterdir():
            state_file = uid_dir / "user_state.json"
            if state_file.exists():
                state = json.loads(state_file.read_text(encoding="utf-8"))
                uid = uid_dir.name
                if uid == user_id or not found:
                    found = True
                    out.append(f"## User: {uid}\n")
                    # Assessment
                    profile = state.get("assessment", {}).get("profile", {})
                    if profile:
                        out.append("### Assessment Profile\n")
                        out.append("| Axis | Score |")
                        out.append("|------|-------|")
                        for axis in ["finger_strength", "pulling_strength", "power_endurance", "technique", "endurance"]:
                            out.append(f"| {axis} | {profile.get(axis, '?')} |")
                        out.append("")

                    # Body
                    body = state.get("assessment", {}).get("body", {})
                    if body:
                        out.append("### Body\n")
                        for k, v in body.items():
                            out.append(f"- {k}: {v}")
                        out.append("")

                    # Goal
                    goal = state.get("goal", {})
                    if goal:
                        out.append("### Goal\n")
                        for k, v in goal.items():
                            out.append(f"- {k}: {v}")
                        out.append("")

                    # Experience
                    exp = state.get("assessment", {}).get("experience", {})
                    if exp:
                        out.append("### Experience\n")
                        for k, v in exp.items():
                            out.append(f"- {k}: {v}")
                        out.append("")

                    # Equipment
                    equip = state.get("equipment", {})
                    if equip:
                        out.append("### Equipment\n")
                        home = equip.get("home", [])
                        if home:
                            out.append(f"- Home: {', '.join(home)}")
                        gyms = equip.get("gyms", [])
                        for g in gyms:
                            out.append(f"- Gym: {g.get('name', '?')} — {', '.join(g.get('equipment', []))}")
                        out.append("")

                    # Preferences
                    prefs = state.get("preferences", {})
                    if prefs:
                        out.append("### Preferences\n")
                        for k, v in prefs.items():
                            out.append(f"- {k}: {v}")
                        out.append("")

                    # Limitations
                    lims = state.get("limitations", {})
                    if lims:
                        out.append("### Limitations\n")
                        out.append(f"```json\n{json.dumps(lims, indent=2)}\n```\n")

                    # Macrocycle
                    macro = state.get("macrocycle", {})
                    if macro:
                        out.append("### Macrocycle\n")
                        out.append(f"- Total weeks: {macro.get('total_weeks', '?')}")
                        out.append(f"- Start date: {macro.get('start_date', '?')}")
                        phases = macro.get("phases", [])
                        if phases:
                            out.append("\n| Phase | Name | Weeks | Start Week | End Week | Intensity Cap |")
                            out.append("|-------|------|-------|------------|----------|---------------|")
                            for p in phases:
                                pid = p.get("phase_id", p.get("id", "?"))
                                pname = p.get("phase_name", "")
                                dur = p.get("duration_weeks", p.get("weeks", "?"))
                                out.append(f"| {pid} | {pname} | {dur} | {p.get('start_week', '?')} | {p.get('end_week', '?')} | {p.get('intensity_cap', '')} |")
                        out.append("")

                    # Baselines
                    baselines = state.get("baselines", {})
                    if baselines:
                        out.append("### Baselines\n")
                        out.append(f"```json\n{json.dumps(baselines, indent=2)}\n```\n")

                    # Trips
                    trips = state.get("trips", [])
                    if trips:
                        out.append("### Trips\n")
                        for t in trips:
                            out.append(f"- {t.get('name', '?')}: {t.get('start', '?')} → {t.get('end', '?')}")
                        out.append("")

                    if uid == user_id:
                        break

    # Also check test fixtures
    fixture = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"
    if fixture.exists():
        state = json.loads(fixture.read_text(encoding="utf-8"))
        out.append("## Test Fixture User State\n")
        profile = state.get("assessment", {}).get("profile", {})
        if profile:
            out.append("### Assessment Profile\n")
            out.append("| Axis | Score |")
            out.append("|------|-------|")
            for axis in ["finger_strength", "pulling_strength", "power_endurance", "technique", "endurance"]:
                out.append(f"| {axis} | {profile.get(axis, '?')} |")
            out.append("")

        body = state.get("assessment", {}).get("body", {})
        if body:
            out.append(f"- Height: {body.get('height_cm', '?')}cm, Weight: {body.get('weight_kg', '?')}kg")

        exp = state.get("assessment", {}).get("experience", {})
        if exp:
            out.append(f"- Climbing years: {exp.get('climbing_years', '?')}, Structured training: {exp.get('structured_training_years', '?')}")

        goal = state.get("goal", {})
        if goal:
            out.append(f"- Goal: {goal.get('type', '?')} {goal.get('target_grade', '?')} by {goal.get('deadline', '?')}")

        grades = state.get("assessment", {}).get("grades", {})
        if grades:
            out.append(f"- Grades: boulder OS={grades.get('boulder_max_onsight', '?')} RP={grades.get('boulder_max_redpoint', '?')}, lead OS={grades.get('lead_max_onsight', '?')} RP={grades.get('lead_max_redpoint', '?')}")

        equip = state.get("equipment", {})
        home = equip.get("home", [])
        if home:
            out.append(f"- Home equipment: {', '.join(home)}")
        gyms = equip.get("gyms", [])
        for g in gyms:
            out.append(f"- Gym: {g.get('name', '?')} — {', '.join(g.get('equipment', []))}")

        lims = state.get("limitations", {})
        if lims:
            out.append(f"- Limitations: {json.dumps(lims)}")

        prefs = state.get("preferences", {})
        if prefs:
            out.append(f"- Finger device: {prefs.get('finger_training_device', '?')}")

        baselines = state.get("baselines", {})
        if baselines:
            out.append(f"\n### Baselines\n```json\n{json.dumps(baselines, indent=2)}\n```")

        macro = state.get("macrocycle", {})
        if macro:
            out.append(f"\n### Macrocycle ({macro.get('total_weeks', '?')} weeks)")
            phases = macro.get("phases", [])
            if phases:
                out.append("| Phase | Weeks |")
                out.append("|-------|-------|")
                for p in phases:
                    pid = p.get("phase_id", p.get("id", "?"))
                    dur = p.get("duration_weeks", p.get("weeks", "?"))
                    out.append(f"| {pid} | {dur} |")
        out.append("")

    if not found and not fixture.exists():
        out.append(f"**User {user_id} not found in local data.**")
        out.append("Production data is on Supabase — run with backend access to extract.\n")

    return "\n".join(out)


def section_process_cues() -> str:
    out = ["# Section 10: PROCESS CUES & COACHING\n"]

    cues = _load_json("backend/catalog/cues/v1/process_cues.json") or []
    out.append(f"Total cues: {len(cues)}\n")

    out.append("## All Process Cues\n")
    out.append("| ID | Text | Session Types | Source |")
    out.append("|----|------|---------------|--------|")
    for c in cues:
        cid = c.get("id", "?")
        text = c.get("text", "?")
        # Truncate long text
        if len(text) > 120:
            text = text[:117] + "..."
        types = ", ".join(c.get("session_types", []))
        source = c.get("source", "")
        out.append(f"| {cid} | {text} | {types} | {source} |")
    out.append("")

    out.append("## Selection Algorithm\n")
    out.append("```")
    out.append("1. Load all cues from process_cues.json (cached via @lru_cache)")
    out.append("2. Filter: cue.session_types contains session_template_id")
    out.append('   Special: if next_day_is_rest → also include "_any_last_session_before_rest" tagged cues')
    out.append('3. Seed = SHA256("{user_id}:{date_str}")')
    out.append("4. Index = seed_int % len(matching_cues)")
    out.append('5. Return {"id": cue.id, "text": cue.text}')
    out.append("```")
    out.append("Properties: stateless, deterministic (same user+date+session = same cue), natural rotation.\n")

    # Phase rationales
    out.append("## Phase Rationale Texts (A141)\n")
    out.append("Located in: `frontend/src/lib/phase-rationales.ts`\n")
    rationales = {
        "base": ("Endurance Base", "Building your aerobic foundation", "6+ weeks low-intensity work for vascular adaptation (angiogenesis, mitochondria). Common mistake: going too hard (>25% MVC = anaerobic)."),
        "strength_power": ("Strength & Power", "Neural horsepower", "Build neural recruitment. High intensity, low volume. Max hang increase 5-10%. Common mistake: adding volume."),
        "power_endurance": ("Power Endurance", "Putting it all together", "Convert base + strength into sustained hard moves. Varied intensity within sessions. Common mistake: all-out on every problem."),
        "performance": ("Performance", "Send season", "Peak readiness. Volume drops, intensity stays. Time to project/onsight. Common mistake: training through it."),
        "deload": ("Deload", "Recovery is training", "Body consolidates gains. Growth hormone surge, tendon repair. 1 week non-negotiable. Common mistake: sneaking in hard sessions."),
    }
    for phase, (title, subtitle, desc) in rationales.items():
        out.append(f"**{phase}** — *{title}: {subtitle}*")
        out.append(f"{desc}\n")

    return "\n".join(out)


def section_load_model() -> str:
    out = ["# Section 11: LOAD MODEL\n"]

    out.append("## Session Load Score\n")
    out.append("- Computed in resolve_session.py")
    out.append("- Formula: `session_load_score = round(min(85, raw_fatigue_sum × 1.5))`")
    out.append("- raw_fatigue_sum = sum of exercise fatigue_cost across all resolved exercises")
    out.append("- Capped at 85\n")

    out.append("## Intensity-to-Load Mapping (planner estimated)\n")
    out.append("| Intensity | Estimated Load |")
    out.append("|-----------|---------------|")
    for intens, load in [("low", 20), ("medium", 40), ("high", 65), ("max", 85)]:
        out.append(f"| {intens} | {load} |")
    out.append("")

    out.append("## Weekly Load Aggregation (report_engine.py)\n")
    out.append("- planned_total = sum(estimated_load_score) across all sessions in week")
    out.append("- actual_total = sum(session_load_score) for done sessions + outdoor_load + free_session_load")
    out.append("- load_ratio = actual_total / planned_total\n")

    out.append("## Free Session Load Formula\n")
    out.append("```")
    out.append("per_climb = relative_difficulty × status_weight × attempt_modifier")
    out.append("load = sum(per_climb) × SCALE_FACTOR")
    out.append("")
    out.append("SCALE_FACTOR = 4.0")
    out.append("relative_difficulty = grade_index / max_grade_index")
    out.append("status_weight: flash=0.8, sent=1.0, attempted=0.6")
    out.append("attempt_modifier: 1 attempt=1.0, 2=1.1, 3+=1.3")
    out.append("Typical: 20 moderate boulders ≈ 40 (medium intensity)")
    out.append("```\n")

    out.append("## Outdoor Load Formula\n")
    out.append("```")
    out.append("load = avg(grade_weight × style_modifier) × volume_factor × duration_factor")
    out.append("Capped at 85")
    out.append("")
    out.append("grade_weight = grade_index(g) + 3")
    out.append("style_modifier: onsight=1.2, flash=1.1, redpoint=1.0, project=0.7, repeat=0.5")
    out.append("volume_factor = min(2.0, 1.0 + log(num_routes, 5))")
    out.append("duration_factor = max(0.5, min(1.5, duration_minutes / 120))")
    out.append("```\n")

    out.append("## Modifiers\n")
    out.append("- Deload factor: 0.5 (applied during deload phase)")
    out.append("- Active limitation: 0.8× load multiplier on affected exercises")
    out.append("- Cooldown fallback: 0.9× multiplier")
    out.append("- Social modifier: NOT YET IMPLEMENTED (planned for Social Session feature)\n")

    return "\n".join(out)


def section_gaps() -> str:
    out = ["# Section 12: IDENTIFIED GAPS (from roadmap)\n"]

    out.append("All items from ROADMAP_CURRENT.md that represent missing training methodology:\n")

    gaps = [
        ("D19", "Simplified linear periodization for beginners", "M", "Longer base, no MaxHangs, more technique. Subsumes D44."),
        ("D34", "EL (Effort Level) as primary intensity metric", "L", "New field on every prescription. Current feedback (very_easy→very_hard) sufficient for launch."),
        ("D44", "ARC ≥6 weeks in Base phase", "S", "Currently base=4wk/floor=2wk. Best via D19 beginner path."),
        ("D45", "ARC <25% MVC formal enforcement", "S", "Currently process cues only. Formal resolver load cap."),
        ("D47", "Varied-intensity intervals (replace 4×4)", "M", "Consuegra Ch.8. 4×4 is industry standard."),
        ("D49", "Don't combine MaxHangs + IntHangs in same mesocycle", "M", "López-Rivera 2018. Planner change."),
        ("D51", "Climbing:conditioning ratio by level", "M", "70/30 → 60/40 → 50/50. Currently template weights only."),
        ("D52", "EL prescription table by experience level", "M", "Depends on D34."),
        ("D14", "López load monitoring (EL trend tracking)", "M", "Depends on D34. Autoregulation."),
        ("D69", "ACWR-based load monitoring", "L", "Needs 4+ weeks data. Overlaps Load Model v2."),
        ("D70", "Overtraining detection heuristics", "M", "5-flag system. Depends on D69."),
        ("D71", "<10% weekly volume increase cap", "S", "Needs historical volume baseline."),
        ("D73", "Technique drill % allocation by level", "M", "Beginners ≥30% drill time."),
        ("D33", "Dedicated generate_warmup() function", "M", "5-phase protocol generator. Current template approach works."),
        ("D20", "Overreach + taper before Performance phase", "M", "+10-15% volume overreach → 40-60% taper."),
        ("D29", "Post-climb mental reflection questions", "S", "5 rotating questions, free text, optional."),
        ("D41", "Campus board auto-stop rules", "S", "RPE check after campus sets."),
        ("D53", "Active recovery progression (3-step)", "S", "References EL system."),
        ("D59", "Hypertonic/inhibited muscle table", "S", "Internal resolver pairing logic."),
    ]

    out.append("| ID | Title | Effort | Notes |")
    out.append("|----|-------|--------|-------|")
    for gid, title, effort, notes in gaps:
        out.append(f"| {gid} | {title} | {effort} | {notes} |")
    out.append("")

    out.append("## Additional gaps (from Engine improvements backlog)\n")
    out.append("- ACWR design needed before Load Model v2")
    out.append("- No overreach detection (readiness score)")
    out.append("- No plateau detection")
    out.append("- No beginner-specific macrocycle path")
    out.append("- No formal climbing:conditioning ratio enforcement")
    out.append("- No technique drill percentage allocation")
    out.append("- No effort level system (EL)")
    out.append("- No ACWR calculation")
    out.append("- No overtraining detection")
    out.append("- No volume increase cap")
    out.append("")

    return "\n".join(out)


# ---------------------------------------------------------------------------
# Assessment section (from assessment_v1.py)
# ---------------------------------------------------------------------------

def section_assessment_appendix() -> str:
    """Appendix: Assessment computation details."""
    out = ["# Appendix A: ASSESSMENT ENGINE (assessment_v1.py)\n"]

    out.append("## 5-Axis Computation\n")

    out.append("### Finger Strength\n")
    out.append("- If max_hang_20mm_7s/5s_total_kg exists: ratio = max_hang / BW, score = (ratio / benchmark) × 100")
    out.append("- Else: grade estimate = (current_idx / target_idx) × 70, minus self-eval penalty")
    out.append("- Self-eval: -15 if primary='fingers_give_out', -8 if secondary\n")

    out.append("### Pulling Strength\n")
    out.append("- If weighted_pullup_1rm_total_kg exists: score = (1RM/BW / benchmark) × 100")
    out.append("- If submaximal data: Brzycki estimate 1RM = weight × 36/(37-reps)")
    out.append("- Else: grade estimate = (current_idx / target_idx) × 65")
    out.append("- Self-eval: -10 if primary='cant_hold_hard_moves', -5 if secondary\n")

    out.append("### Power Endurance\n")
    out.append("Three-component weighted score:")
    out.append("- Gap score (40%/60%): RP-OS grade gap → 75/55/40/30 for gap ≤2/3-4/5-6/>6")
    out.append("- Repeater test (40%/0%): reps / benchmark × 100")
    out.append("- Self-eval (20%/40%): -8 primary / -4 secondary for 'pump_too_early'\n")

    out.append("### Technique\n")
    out.append("- RP-OS gap: 80/60/40/30 for gap ≤2/3-4/5-6/>6")
    out.append("- Self-eval: -10 primary / -5 secondary for 'technique_errors' or 'cant_read_routes'\n")

    out.append("### Endurance\n")
    out.append("- Base = PE_score × 0.8")
    out.append("- Experience bonus: min(climbing_years × 2, 10)")
    out.append("- Max hang duration: ≥90s=+8, ≥60s=+4, ≥45s=0, ≥30s=-4, <30s=-8")
    out.append("- Self-eval: -10/-5 for 'pump_too_early', -10/-5 for 'cant_manage_rests'\n")

    out.append("## Benchmark Tables\n")
    out.append("### Finger Benchmark (max hang 20mm / BW ratio)\n")
    out.append("| Grade | Ratio |")
    out.append("|-------|-------|")
    fb = {"7a": 1.0, "7a+": 1.08, "7b": 1.15, "7b+": 1.20, "7c": 1.25, "7c+": 1.30,
          "8a": 1.40, "8a+": 1.50, "8b": 1.60, "8b+": 1.70, "8c": 1.80, "8c+": 1.90,
          "9a": 2.00, "9a+": 2.10}
    for g, r in fb.items():
        out.append(f"| {g} | {r} |")
    out.append("")

    out.append("### Pulling Benchmark (weighted pullup 1RM / BW ratio)\n")
    out.append("| Grade | Ratio |")
    out.append("|-------|-------|")
    pb = {"7a": 1.20, "7a+": 1.25, "7b": 1.30, "7b+": 1.35, "7c": 1.40, "7c+": 1.45,
          "8a": 1.55, "8a+": 1.65, "8b": 1.75, "8b+": 1.85, "8c": 1.95, "8c+": 2.05,
          "9a": 2.15, "9a+": 2.25}
    for g, r in pb.items():
        out.append(f"| {g} | {r} |")
    out.append("")

    out.append("### PE Repeater Benchmark (7:3 duty, 20mm, 60% max — expected reps)\n")
    out.append("| Grade | Reps |")
    out.append("|-------|------|")
    pe = {"7a": 18, "7a+": 20, "7b": 22, "7b+": 24, "7c": 26, "7c+": 28,
          "8a": 30, "8a+": 32, "8b": 34, "8b+": 36, "8c": 38, "8c+": 40,
          "9a": 42, "9a+": 44}
    for g, r in pe.items():
        out.append(f"| {g} | {r} |")
    out.append("")

    return "\n".join(out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Extract audit snapshot of climb-agent engine")
    parser.add_argument("--user-id", default="7ea9f0ee-e629-4ce9-8f4f-f8e6e3dc771e",
                        help="User ID for Section 9 (default: Daniele's ID)")
    parser.add_argument("--output", default=None,
                        help="Output path (default: docs/audit_snapshot_YYYY-MM-DD.md)")
    args = parser.parse_args()

    today = date.today().isoformat()
    output_path = args.output or f"docs/audit_snapshot_{today}.md"
    output_path = REPO_ROOT / output_path

    header = f"""# climb-agent — Engine Audit Snapshot

> Generated: {today}
> Script: `scripts/extract_audit_snapshot.py`
> Purpose: Comprehensive engine state for literature audit

---

"""

    sections = [
        section_macrocycle(),
        section_planner(),
        section_session_catalog(),
        section_template_catalog(),
        section_exercise_catalog(),
        section_resolver(),
        section_progression(),
        section_safety(),
        section_user_state(args.user_id),
        section_process_cues(),
        section_load_model(),
        section_gaps(),
        section_assessment_appendix(),
    ]

    content = header + "\n---\n\n".join(sections)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    # Count stats
    raw_ex = _load_json("backend/catalog/exercises/v1/exercises.json") or {}
    exercises = raw_ex.get("exercises", raw_ex) if isinstance(raw_ex, dict) else raw_ex
    sessions_dir = REPO_ROOT / "backend" / "catalog" / "sessions" / "v1"
    session_count = len(list(sessions_dir.glob("*.json")))
    templates_dir = REPO_ROOT / "backend" / "catalog" / "templates" / "v1"
    template_count = len(list(templates_dir.glob("*.json")))

    print(f"Snapshot saved: {output_path}")
    print(f"Snapshot complete: {len(exercises)} exercises, {session_count} sessions, {template_count} templates")
    print(f"Sections: {len(sections)} (including Appendix A)")

    return str(output_path)


if __name__ == "__main__":
    main()
