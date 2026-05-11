# B208 — Planner equipment-only: eliminate `_expand_session_locations`

**Severity:** P1
**Type:** B (bugfix — root-cause)
**Module:** `backend/engine/planner_v2.py` (STOP-gate required per CLAUDE.md)
**Upstream of:** B206 (resolver symptom fix — already shipped)
**Surfaced by:** Daniele 2026-04-17 `finger_maintenance_gym` case, verified in D210.

---

## 1. What B206 fixed vs what B208 must fix

B206 corrected the **resolver** (`resolve_session.py`) so that when `user_state.context.location="home"` and `session.context.location="gym"`, the resolver trusts user_state. This masked the downstream symptom — `aerobic_pyramid_intervals` no longer surfaces.

B206 did **not** touch the upstream cause: the planner itself silently re-routes `*_gym` sessions to home slots via `_expand_session_locations()`. The location mismatch that B206 patches around is **created by the planner**, not by the catalog. Every time a new gym session is added to the catalog, the same class of bug can re-emerge.

**B208 closes the hole at the source.**

---

## 2. Current behavior — `_expand_session_locations` (`planner_v2.py:145-161`)

```python
def _expand_session_locations(
    session_locations: Tuple[str, ...],
    required_equipment: Optional[List[str]],
    home_equipment: Optional[List[str]],
) -> Tuple[str, ...]:
    if "home" in session_locations:
        return session_locations
    if not home_equipment or not required_equipment:
        return session_locations
    home_eq = set(expand_equipment(home_equipment))
    if all(eq in home_eq for eq in required_equipment):
        return tuple(session_locations) + ("home",)   # silently adds "home"
    return session_locations
```

**Rule**: if **every** required-equipment item exists at home, inject `"home"` into the session's viable locations — regardless of author intent.

**Two call-sites**, both in the slot-placement flow:
- `planner_v2.py:482` — inside `_find_slot()` (Pass 1/2/2.5 slot discovery)
- `planner_v2.py:517` — inside `_make_session_entry()` (final slot assignment)

**Downstream consumer**: `_pick_location()` (`planner_v2.py:258-295`) intersects `effective_locations` with `slot_locations` + `allowed_locations`, then applies `preferred_location` and equipment gating via `_location_has_equipment()`.

### Why this over-reaches

The original B137 intent (2026-03-21) was narrow: **homewall/board users should still get climbing sessions at home** when they have no gym, because at the time the catalog only had `*_gym` climbing sessions. The function correctly handles that case.

But the filter is written too broadly — it triggers whenever **any** `required_equipment` list is satisfied at home. This includes `["hangboard"]`-only sessions, which:
- Have no wall-surface requirement
- Are authored with `location=("gym",)` for a reason: gym warmup templates assume gym-context equipment (`warmup_climbing` pulls `warmup_easy_boulders`, which wants `gym_boulder`/`board_*`/`spraywall`)

Result: `finger_maintenance_gym` (req=`["hangboard"]`) gets re-routed to home → resolver fills from home equipment → warmup block breaks (pre-B206: picked wall-only `aerobic_pyramid_intervals`; post-B206: surfaces `warmup_easy_boulders` as incompat — the residual B207 finding).

### Real bug-class map

| Session | req_equipment | `_expand` injects home? | Home-compatible? |
|---|---|---|---|
| `finger_maintenance_gym` | `[hangboard]` | ✅ yes (wrong) | warmup breaks |
| `power_endurance_gym` | `[gym_boulder]` | only with homewall/board | ✅ legit B137 case |
| `pulling_strength_gym` | `[pullup_bar]` | ✅ yes | ambiguous |
| `heavy_conditioning_gym` | `[dumbbell]` | ✅ yes (if home has dumbbell) | ambiguous |
| `route_endurance_gym` | `[gym_routes]` | only with board equivalence | legit but edge-case |
| `endurance_aerobic_gym` | `[gym_routes]` | only with board equivalence | legit but edge-case |

Sessions in rows 1, 3, 4 are the silent-reroute class. They share: `location=("gym",)`, non-wall `required_equipment`, available at home.

---

## 3. Call-site map + test coverage

**Production call-sites** (single module):
- `planner_v2.py:482` — `_find_slot()` — used by Pass 1, Pass 2, Pass 2.5
- `planner_v2.py:517` — `_make_session_entry()` — used by every session placement

**Test coverage** (dedicated):
- `backend/tests/test_planner_v2.py:941-1030` — `TestPlannerV2HomewallExpansion`
  - `test_homewall_gets_climbing_sessions_at_home` — asserts homewall user gets `gym_boulder` sessions on home days
  - `test_no_homewall_no_climbing_at_home` — asserts no expansion without homewall
  - `test_route_sessions_not_at_home_with_homewall` — asserts `gym_routes` sessions don't leak to home (homewall ≠ routes)
- `backend/tests/test_b159_boulder_surface_equivalence.py` — board_kilter/moonboard/other → gym_boulder via `expand_equipment()`
- `backend/tests/test_resolver_p0.py` — post-B206, validates resolver picks correct location

**Implicit coverage**: every planner integration test that places gym sessions. None will fail if the function becomes stricter (all existing tests use either homewall/board setups or gym-only users).

---

## 4. Design options

### Option A — Targeted narrow scope (minimal diff)

Only expand to home when `required_equipment` includes a **wall surface**. Preserves B137 intent. Blocks the `hangboard`/`pullup_bar`/`dumbbell` silent-reroute class.

```python
_WALL_SURFACES: frozenset[str] = frozenset({
    "gym_boulder", "gym_routes", "spraywall",
    "board_kilter", "board_moonboard", "board_other", "homewall",
})

def _expand_session_locations(session_locations, required_equipment, home_equipment):
    if "home" in session_locations:
        return session_locations
    if not home_equipment or not required_equipment:
        return session_locations
    req_set = set(required_equipment)
    if not (req_set & _WALL_SURFACES):
        return session_locations   # non-wall sessions: trust catalog intent
    home_eq = set(expand_equipment(home_equipment))
    if all(eq in home_eq for eq in required_equipment):
        return tuple(session_locations) + ("home",)
    return session_locations
```

- **Pros**: smallest diff, preserves B137 tests as-is, fixes the bug class.
- **Cons**: function is still "magic". Future session authors may still be surprised by location switching when a session happens to require wall + home has board.
- **Tests**: add ≥2 regression cases (`finger_maintenance_gym` w/ hangboard-home stays gym; hangboard-only user → session skipped, not routed home).

### Option B — Eliminate (catalog-authoritative)

Remove `_expand_session_locations` entirely. `_SESSION_META[*].location` is the single source of truth. If a user has no gym, gym sessions are simply unviable (planner falls back to the `_CLIMBING_FALLBACKS` chain).

- Requires: either mark existing `*_gym` sessions that are homewall-viable as `location=("gym", "home")` in `_SESSION_META` (explicit authoring), OR create `*_homewall` session variants and swap via a catalog rule. Homewall/board users would need their climbing sessions declared `location=("gym", "home")`.
- **Pros**: removes all hidden behavior. Catalog tells the whole story. Aligns with CLAUDE.md equipment principle (we filter on required_equipment, but we also respect declared location).
- **Cons**: B137 tests break until catalog is updated. Requires catalog audit (6-8 sessions). Homewall users could lose climbing coverage if catalog update is incomplete.
- **Tests**: migrate `TestPlannerV2HomewallExpansion` to assert catalog-declared viability instead of inferred expansion.

### Option C — Full equipment-only refactor

Remove the `location` tuple from `_SESSION_META` entirely. Planner decides viability purely from `required_equipment` vs slot-level equipment (home_equipment for home slots, gym equipment for gym slots).

- **Pros**: maximal adherence to equipment-only principle. Single source of truth = `required_equipment`.
- **Cons**: large refactor. `_pick_location` logic changes. Session authoring semantics change (`*_gym` naming becomes descriptive only). Likely 50+ test updates. Does NOT interact well with cases like `route_endurance_gym` (requires `gym_routes` — which only exists at gym by definition, so it is implicitly gym-only even without the `location` field — but then boarding cases need explicit equipment mapping).

---

## 5. Recommendation

**Ship Option A first**. It's the minimum viable fix for the P1 bug class, preserves B137 homewall coverage, and leaves Option B/C as a future refactor once catalog authoring semantics are discussed (likely bundled with B207 `warmup_climbing` template hardening).

Rationale:
- Option A: 1 function modified, 2 new regression tests, zero catalog changes. Can ship today.
- Option B: requires catalog co-design with B207. Better as a joint brief B207+B209.
- Option C: not justified without a broader refactor thesis (R147 already in roadmap).

If Daniele disagrees on Option A's "magic" concern, **switch to Option B** and accept the 1-2 day catalog audit cost.

---

## 6. Acceptance criteria (Option A)

- [ ] `_expand_session_locations` only expands when `required_equipment ∩ _WALL_SURFACES ≠ ∅`.
- [ ] New regression test: `finger_maintenance_gym` with Daniele's home equipment (`hangboard, pullup_bar, band, …`, no wall) — session is placed at **gym** slot (or not at all if no gym slot available), never at home.
- [ ] New regression test: user with `hangboard` + no wall + no gym — `finger_maintenance_gym` is **not** scheduled; planner falls back to `finger_maintenance_home` or skips.
- [ ] Existing `TestPlannerV2HomewallExpansion` continues to pass unchanged (homewall users still get boulder at home).
- [ ] Existing B159 boulder-surface-equivalence tests pass unchanged.
- [ ] D210 production regression: re-run `/tmp/d210/prod_harness.py` against post-B208 main. Expected: zero new incompat exercises, zero location drift on non-`finger_maintenance_gym` sessions.
- [ ] All 1659 tests pass.

---

## 7. Non-goals / follow-ups

- **Not** touching the catalog `location` field in session JSON files (already stripped in B206).
- **Not** removing `_SESSION_META.location` duplication (tracked in D209, not urgent).
- **Not** fixing `warmup_climbing` template bypass for `warmup_easy_boulders` — that's B207 and independent of location routing.
- After B208 ships, re-check the Daniele `regeneration_easy` 2026-04-15 discrepancy (`planner=home, resolved=gym`, pre-B206 cached) — it's a done session, immutable, but confirms the pattern.

---

## 8. STOP-gate protocol (per CLAUDE.md)

1. **Phase 0 (this document)** — analysis + options. DONE.
2. **Phase 1 — await Daniele's OK on scope** (Option A vs B vs C).
3. **Phase 2 — implement** after explicit approval.
4. **Phase 3 — verify** full test suite + D210 prod re-run.

**Do NOT proceed to Phase 2 without Daniele's written OK.**
