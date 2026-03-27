# Mega-Brief Session 2 — Pre-Launch Patch
> **Date:** 2026-03-23
> **Purpose:** 4 corrections to apply to `claude_code_mega_brief_v1.md` BEFORE launching Session 2
> **Format:** Exact FIND/REPLACE blocks for the implementation project
> **Status:** ⏸️ Ready to apply — waiting for Session 2 launch

---

## Patch D11 — Missing edge size preference note

**Context:** D11 (warm-up repeaters on large edge) doesn't specify what "large" means relative to the user's preference.

**FIND:**
```
Edge size: ≥20 mm (or user's preferred warm-up edge)
```

**REPLACE:**
```
Edge size: ≥20 mm (or user's preferred warm-up edge). If the user's hangboard has only one edge size, use that. If multiple edges available, prefer the largest edge ≥20mm. Never prescribe warm-up repeaters on an edge smaller than 20mm.
```

---

## Patch D12 — Rest time range correction

**Context:** D12 (density_hangs corrections) originally specified 60–120s rest. Primary sources (Nelson C4HP, López-Rivera) use 120–300s for strength-oriented hangs.

**FIND:**
```
Rest between sets: 60-120 seconds
```

**REPLACE:**
```
Rest between sets: 120-300 seconds (per Nelson C4HP and López-Rivera primary protocols). The 60-120s range was an error — it applies to repeaters/endurance hangs, not max strength density hangs.
```

---

## Patch D39 — Risk of accidental deletion of band-assisted pull-ups

**Context:** D39 prescribes eccentric pull-ups for beginners instead of band-assisted. But the brief's wording could be misread as "delete band-assisted pull-ups from the catalog entirely" rather than "don't prescribe them as the default for beginners."

**FIND:**
```
Replace band-assisted pull-ups with eccentric pull-ups as the default beginner pulling exercise.
```

**REPLACE:**
```
Set eccentric pull-ups as the DEFAULT beginner pulling exercise (instead of band-assisted pull-ups). Keep band-assisted pull-ups in the catalog as an alternative — they remain valid for users who explicitly prefer them or who cannot perform controlled eccentrics. The change is to the default selection logic, not the catalog contents.
```

---

## Patch D72 — Ambiguous full crimp guidance

**Context:** D72 says "open-hand grip default for all hangboard training" but the surrounding text in `02_finger_strength.md` says "Add full crimp cautiously for advanced climbers" which could be misread as applying to hangboard training.

**FIND:**
```
Default grip type for all hangboard exercises: open-hand (half crimp acceptable as progression).
Full crimp is never prescribed on the hangboard.
```

**REPLACE:**
```
Default grip type for all hangboard exercises: open-hand (half crimp acceptable as progression).
Full crimp is NEVER prescribed on the hangboard — this is a hard safety rule with no exceptions.
Full crimp IS acceptable during on-wall climbing (bouldering, route climbing) where the climber
naturally selects grip type. The distinction is: engine-prescribed hangboard = never full crimp;
self-directed climbing on wall = climber's choice.
```

---

*End of Session 2 pre-launch patch — 4 corrections*
