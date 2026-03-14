# Audit: Location vs Equipment — Session Filtering

> Date: 2026-02-27
> Context: Base phase session distribution audit, Step 5
> Status: Analysis only — no code changes

---

## Full Session Table (25 active sessions)

| session_id | location META | equipment chiave | home + hangboard? | home + board? | vincolo reale |
|---|---|---|---|---|---|
| strength_long | gym, home | hangboard | ⚠️ parziale (skip climbing block) | ⚠️ parziale | climbing_movement richiede parete |
| power_contact_gym | gym | gym_boulder | ❌ | ❌ | limit bouldering su parete fresca |
| power_endurance_gym | gym | gym_routes | ❌ | ⚠️ (4×4 su board) | route intervals primario |
| endurance_aerobic_gym | gym | gym_routes | ❌ | ⚠️ (ARC su board) | volume continuo su vie |
| technique_focus_gym | gym | gym_boulder | ❌ | ⚠️ (drill su board) | drill tecnici su parete |
| route_endurance_gym | gym | gym_routes | ❌ | ⚠️ (endurance hangs) | threshold su vie |
| easy_climbing_deload | gym | gym_boulder | ❌ | ⚠️ (easy board) | climbing leggero |
| regeneration_easy | gym | gym_boulder | ❌ | ⚠️ (easy board) | continuity climbing |
| finger_maintenance_gym | gym | hangboard + parete | ⚠️ (skip climbing) | ⚠️ | repeaters + easy climbing |
| pulling_strength_gym | gym | pullup_bar | ✅ (con sbarra) | ✅ | weighted pullup, lock-off |
| heavy_conditioning_gym | gym | dumbbell | ✅ (con manubri) | ✅ | row, press, carry |
| lower_body_gym | gym | dumbbell | ✅ (con manubri) | ✅ | squat, RDL unilaterali |
| finger_strength_home | home | hangboard | ✅ | ✅ | — |
| finger_maintenance_home | home | hangboard | ✅ | ✅ | — |
| finger_aerobic_base | home | hangboard | ✅ | ✅ | — |
| finger_endurance_short | home | hangboard | ✅ | ✅ | — |
| test_max_hang_5s | home, gym | hangboard | ✅ | ✅ | — |
| test_repeater_7_3 | home, gym | hangboard | ✅ | ✅ | — |
| test_max_weighted_pullup | home, gym | pullup_bar | ✅ (con sbarra) | ✅ | — |
| complementary_conditioning | home, gym | dumbbell (opz.) | ✅ | ✅ | bodyweight fallback |
| prehab_maintenance | home, gym | nessuno | ✅ | ✅ | — |
| flexibility_full | home, gym | nessuno | ✅ | ✅ | — |
| handstand_practice | home, gym | nessuno (muro opz.) | ✅ | ✅ | — |
| deload_recovery | home, gym | nessuno | ✅ | ✅ | — |
| yoga_recovery | home | nessuno | ✅ | ✅ | — |

---

## Categorization: Why gym-only?

| Motivo | Sessioni | Replicabile a casa? |
|---|---|---|
| **gym_routes** (vie) | power_endurance_gym, endurance_aerobic_gym, route_endurance_gym | ❌ Non replicabile |
| **gym_boulder** (parete) | power_contact_gym, technique_focus_gym, easy_climbing_deload, regeneration_easy | ⚠️ Con board (stimolo diverso) |
| **equipment gym** (no parete) | pulling_strength_gym, heavy_conditioning_gym, lower_body_gym | ✅ Con attrezzatura casa (sbarra/manubri) |

**Summary:**
- 3 sessions → gym_routes (not replicable at home)
- 4 sessions → gym_boulder (partially replicable with climbing board)
- 3 sessions → gym equipment only, no wall needed (replicable with pullup bar + dumbbells)
- 15 sessions → already home-viable

---

## Proposed Architecture: Equipment-based filtering (ARCH-1)

### Problem

The planner uses `location` ("gym" / "home") as a hard filter in `_SESSION_META`. This is too coarse:
- `pulling_strength_gym` says "gym" but only needs a pullup bar
- `heavy_conditioning_gym` says "gym" but only needs dumbbells
- A user with a pullup bar at home can never get `pulling_strength_gym` in a home slot

### Proposed model

Replace `location` with `required_equipment_any` (OR logic) per session. Derive location viability at runtime from the user's equipment.

```python
# Today (location-based):
"pulling_strength_gym": { "location": ("gym",) }

# Proposed (equipment-based):
"pulling_strength_gym": { "required_equipment_any": ["pullup_bar"] }
```

### How it would work

1. **User state** already has `equipment.home` and `equipment.gyms[].equipment` — no schema change needed
2. Each session in `_SESSION_META` declares `required_equipment_any: [...]` (OR: at least 1 match required)
3. Planner, given a slot with `location=home`, filters sessions where `set(session.required_equipment_any) & set(user.equipment.home) != empty`
4. For `location=gym`, same logic with `gyms[gym_id].equipment`
5. Sessions without `required_equipment_any` (prehab, flexibility, deload) → available everywhere
6. **Backward compatible**: `location` remains as default hint, `required_equipment_any` overrides if present

### Benefits

- `pulling_strength_gym` appears in home slots if user has `pullup_bar` at home
- `heavy_conditioning_gym` appears at home if user has `dumbbell`
- Planner doesn't need to know "what gym means" — it deduces from equipment
- Eliminates need to duplicate sessions by location (e.g., finger_maintenance_home vs finger_maintenance_gym)

### Risks

- Requires equipment audit on all 25 sessions (not all JSONs have coherent `required_equipment`)
- Session names with `_gym`/`_home` suffix become misleading
- Needs test coverage to verify equipment filter doesn't break existing phase pools

### Effort estimate

Medium — changes to `planner_v2.py` (filter logic), `_SESSION_META` (new field), and tests. No changes to resolver or macrocycle.
