"""B157: Catalog validation tests — domain, role, and orphan-leak prevention."""

import json
import glob
import os

import pytest

EXERCISES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "catalog", "exercises", "v1", "exercises.json"
)
TEMPLATES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "catalog", "templates", "v1"
)
SESSIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "catalog", "sessions", "v1"
)

CANONICAL_DOMAINS = {
    "finger_strength", "finger_max_strength", "finger_strength_endurance",
    "finger_aerobic_endurance", "power", "power_endurance", "strength_general",
    "aerobic_capacity", "anaerobic_capacity", "core", "mobility",
    "prehab_elbow", "prehab_finger", "prehab_shoulder", "prehab_wrist",
    "contact_strength", "regeneration", "flexibility", "handstand_skill",
    "technique_boulder", "technique_lead", "technique_footwork",
    "technique_body_position", "technique_constraint", "technique_movement",
    "technique_relaxation", "endurance", "climbing_routes",
    "lock_off_endurance", "strength_pulling",
}

CANONICAL_ROLES = {
    "warmup", "activation", "main", "accessory", "cooldown",
    "prehab", "technique", "conditioning", "test", "recovery",
}


def _load_exercises():
    with open(EXERCISES_PATH) as f:
        data = json.load(f)
    return data["exercises"] if isinstance(data, dict) else data


def _load_templates():
    templates = []
    for path in sorted(glob.glob(os.path.join(TEMPLATES_DIR, "*.json"))):
        with open(path) as f:
            templates.append(json.load(f))
    return templates


def _load_sessions():
    sessions = []
    for path in sorted(glob.glob(os.path.join(SESSIONS_DIR, "*.json"))):
        with open(path) as f:
            sessions.append(json.load(f))
    return sessions


# ---------------------------------------------------------------------------
# Test 1: all exercise domains are canonical
# ---------------------------------------------------------------------------
def test_all_exercise_domains_are_canonical():
    """Every domain value in every exercise must be in vocabulary §2.2 canonical set."""
    exercises = _load_exercises()
    violations = []
    for e in exercises:
        domains = e.get("domain", [])
        if isinstance(domains, str):
            domains = [domains]
        bad = [d for d in domains if d not in CANONICAL_DOMAINS]
        if bad:
            violations.append(f"{e['id']}: {bad}")
    assert violations == [], f"Non-canonical domains:\n" + "\n".join(violations)


# ---------------------------------------------------------------------------
# Test 2: all exercise roles are canonical
# ---------------------------------------------------------------------------
def test_all_exercise_roles_are_canonical():
    """Every role value in every exercise must be in vocabulary §2.1 canonical set."""
    exercises = _load_exercises()
    violations = []
    for e in exercises:
        roles = e.get("role", [])
        if isinstance(roles, str):
            roles = [roles]
        bad = [r for r in roles if r not in CANONICAL_ROLES]
        if bad:
            violations.append(f"{e['id']}: {bad}")
    assert violations == [], f"Non-canonical roles:\n" + "\n".join(violations)


# ---------------------------------------------------------------------------
# Test 3: no test exercise selected by non-test block
# ---------------------------------------------------------------------------
def test_no_test_exercise_selected_by_non_test_block():
    """No template/session block without explicit role:test should be able to select
    a role:test exercise via domain-only matching.

    Checks that every block either:
    - Has an explicit exercise_id, OR
    - Has a role filter that does NOT include 'test', OR
    - Has role filter that explicitly includes 'test' (intentional)

    A block with NO role filter is vulnerable to selecting test exercises.
    """
    violations = []

    # Check template blocks
    for tmpl in _load_templates():
        tid = tmpl.get("id", "???")
        for block in tmpl.get("blocks", []):
            bid = block.get("block_id", "???")
            if block.get("exercise_id"):
                continue  # explicit selection — safe
            roles = block.get("role", [])
            if isinstance(roles, str):
                roles = [roles]
            if not roles:
                violations.append(f"template {tid}/{bid}: no role filter (leak risk)")

    # Check session inline modules (those with selection but no template_id)
    for sess in _load_sessions():
        sid = sess.get("id", "???")
        for mod in sess.get("modules", []):
            if "template_id" in mod:
                continue
            bid = mod.get("block_id", "???")
            sel = mod.get("selection", {})
            prim = sel.get("primary", {})
            filters = prim.get("filters", {})
            if not filters:
                continue  # no selection filters at all — uses different path
            role_filter = filters.get("role", [])
            if isinstance(role_filter, str):
                role_filter = [role_filter]
            if not role_filter:
                violations.append(
                    f"session {sid}/{bid}: inline block has filters but no role filter (leak risk)"
                )

    assert violations == [], (
        "Blocks without role filter can select test exercises:\n"
        + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# Test 4: template domain filters use canonical values
# ---------------------------------------------------------------------------
def test_template_domain_filters_use_canonical_values():
    """Every domain value in template block filters must be in vocabulary §2.2."""
    violations = []

    for tmpl in _load_templates():
        tid = tmpl.get("id", "???")
        for block in tmpl.get("blocks", []):
            bid = block.get("block_id", "???")
            # Block-level domain
            dom = block.get("domain", [])
            if isinstance(dom, str):
                dom = [dom]
            bad = [d for d in dom if d not in CANONICAL_DOMAINS]
            if bad:
                violations.append(f"template {tid}/{bid} domain: {bad}")

    for sess in _load_sessions():
        sid = sess.get("id", "???")
        for mod in sess.get("modules", []):
            if "template_id" in mod:
                continue
            bid = mod.get("block_id", "???")
            sel = mod.get("selection", {})
            prim = sel.get("primary", {})
            filters = prim.get("filters", {})
            fdom = filters.get("domain", [])
            if isinstance(fdom, str):
                fdom = [fdom]
            bad = [d for d in fdom if d not in CANONICAL_DOMAINS]
            if bad:
                violations.append(f"session {sid}/{bid} filter.domain: {bad}")

    assert violations == [], (
        "Non-canonical domain values in filters:\n" + "\n".join(violations)
    )
