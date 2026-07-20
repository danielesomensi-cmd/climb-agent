# Coach KB — Routing Index

> **Generated:** A-COACH-KB-V1 (2026-05-19) from audit `docs/research_kb/coach_kb_v1_audit.md` §4.6.
> **Purpose:** Keyword-based router. Maps user-intent vocabulary to the L3 files that contain grounding evidence.
> **Loader behavior:** match user message against keyword sets below. Load top 1-3 matched L3 files alongside the always-loaded L0+L1+L2 layers (~5.1k tokens). Hard cap: 3 L3 files per request.

---

## Always-loaded layers (every request)

| Path | Purpose | Token estimate |
|---|---|---|
| `L0_safety_hard_rules.md` | Non-negotiable safety boundaries (11 rules) | ~900 |
| `L1_coach_voice.md` | Voice, tone, citation style, sensitive-topic protocols, CPHWA format | ~1,200 |
| `L2_decision_index.md` | Dense decision index (35 entries) — coach's quick-reference for "why" questions | ~3,000 |

**Subtotal always-loaded: ~5,100 tokens.**

---

## Keyword routing map (L3)

| User intent / keywords | Route to | UC# | Token estimate |
|---|---|---|---|
| "phase", "deload", "macrocycle", "periodization", "4-3-2-1", "DUP", "base", "build", "peak", "fase", "scarico", "macrociclo", "periodizzazione", "picco" | `L3/01_periodization.md` | UC1 | ~6,000 |
| "hangboard", "max hang", "repeater", "edge", "finger strength", "no-hang", "lifting edge", "abrahangs", "MVC", "trave", "travetta", "sospensioni", "forza dita", "tacca", "svaso", "pinza" | `L3/02_finger_strength.md` | UC2 | ~7,000 |
| "pull-up", "pulling", "weighted pull", "lock-off", "contact strength", "trazioni", "trazione", "bloccaggio" | `L3/03_pulling_strength.md` | UC3 | ~3,500 |
| "4×4", "4x4", "intervals", "power endurance", "PE", "pump training", "linked problems", "resistenza alla forza", "intervalli", "pompa" | `L3/04_power_endurance.md` | UC4 | ~4,000 |
| "ARC", "endurance", "capillaries", "aerobic", "critical force", "CF test", "resistenza", "aerobico", "capillari" | `L3/05_aerobic_endurance_arc.md` | UC5 | ~3,500 |
| "technique", "drill", "footwork", "silent feet", "movement", "skill", "motor learning", "tecnica", "piedi", "movimento" | `L3/06_technique_movement.md` | UC6 | ~7,000 |
| "fear", "falling", "head game", "focus", "anxiety", "mental", "redpoint" (mental context), "paura", "volo", "ansia", "mentale" | `L3/07_mental_fear_focus.md` | UC7 | ~6,000 |
| "eat", "nutrition", "macros", "supplement", "creatine", "collagen", "protein", "carbs", "weight", "mangiare", "nutrizione", "alimentazione", "integratori", "proteine", "carboidrati" | `L3/08_nutrition.md` | UC8 | ~4,000 |
| "recovery", "sleep", "rest day", "G-Tox", "active rest", "recupero", "sonno", "riposo", "dormire" | `L3/09_recovery_sleep.md` | UC9 | ~4,000 |
| "pulley", "finger pain", "tweak", "lumbrical", "A2", "A4", "tendon", "crimp injury", "puleggia", "dolore", "tendine", "infortunio", "dita", "tacca" | `L3/10_injuries_fingers.md` | UC10 | ~6,000 |
| "shoulder", "elbow", "epicondylitis", "rotator cuff", "scapular", "impingement", "spalla", "gomito", "cuffia dei rotatori", "dolore" | `L3/11_injuries_shoulder_elbow.md` | UC11 | ~5,000 |
| "antagonist", "postural", "extensor", "climber's back", "prehab", "antagonisti", "posturale", "postura", "estensori" | `L3/12_antagonist_postural.md` | UC12 | ~4,500 |
| "trip", "taper", "redpoint" (prep context), "peak", "performance phase", "Ceuse", "outdoor send", "lavorato", "progetto", "trasferta", "a vista" | `L3/13_tapering_redpoint.md` | UC13 | ~3,000 |
| "cycle", "menstrual", "female", "woman", "youth", "kid", "teen", "older", "40+", "age", "ciclo mestruale", "mestruale", "donna", "giovani", "adolescente", "anziano" | `L3/14_female_age_youth.md` | UC14 | ~4,000 |
| "goal", "motivation", "plateau", "why train", "values", "intrinsic", "obiettivo", "motivazione", "stallo", "valori" | `L3/15_goal_setting_motivation.md` | UC15 | ~3,000 |
| "MVC", "score", "BW", "percentile", "test result", "assessment", "5-axis", "radar", "valutazione", "punteggio" | `L3/16_assessment_interpretation.md` | UC18 | ~3,500 |
| "tired", "ready", "RPE", "overtraining", "ACWR", "feel off", "HRV", "resting HR", "stanco", "stanchezza", "sovrallenamento", "affaticato" | `L3/17_readiness_overtraining.md` | UC17/UC21 | ~3,500 |
| "no hangboard", "alternative", "travel", "home gym", "minimum", "no equipment", "alternativa", "senza trave", "senza attrezzatura", "in viaggio" | `L3/18_equipment_fallback.md` | UC19 | ~3,000 |
| "work", "running", "lifting", "other sport", "stress", "lifestyle", "concurrent", "lavoro", "corsa", "altro sport" | `L3/19_lifestyle_integration.md` | UC22 | ~3,000 |
| "back to training", "break", "off", "detraining", "return", "restart", "illness", "injury return", "ripresa", "ritorno", "pausa", "malattia", "infortunio" | `L3/20_return_to_training.md` | UC23 | ~3,000 |
| "gym", "bench", "dumbbell", "dumbbells", "barbell", "machine", "weights", "workout", "swap", "bored", "build me a session", "commercial gym", "regular gym", "work gym", "don't feel like", "not feeling it", "rather do", "leg day", "upper body", "general strength", "palestra", "pesi", "manubri", "bilanciere", "panca", "creami una sessione", "non mi va", "gambe" | `L3/21_adhoc_gym_sessions.md` | UC24/UC25 | ~3,800 |

---

## Routing rules

1. **Tokenize** the user message (case-insensitive).
2. **Match** each L3 row's keyword set; count keyword occurrences (any match counts as +1, multiple keywords in same row count once).
3. **Rank** matched rows by count descending; ties broken by row order in this file.
4. **Cap at 3 files**. If 4+ tie at top, trim by dropping rows tied at the lowest count.
5. **Fallback** if zero match: load `L3/01_periodization.md` + `L3/15_goal_setting_motivation.md` as generic defaults.
6. **Cross-file dependencies**: if a query routes to `10_injuries_fingers` AND the user mentions an exercise/test (e.g. "max hang"), additionally co-load `02_finger_strength` (capped within the 3-file limit).

---

## Token budget reference

| Scenario | Always-loaded | L3 | Engine state + history | Total input |
|---|---|---|---|---|
| Typical 1-file query | 5,100 | ~5,000 | ~3,000 | **~13,000** |
| 2-file cross-domain | 5,100 | ~10,000 | ~3,000 | **~18,000** |
| Worst-case 3-file | 5,100 | ~22,000 | ~5,000 | **~32,000** |

Output target per coach response: 300-800 tokens.

---

## Versioning

| Version | Date | Change |
|---|---|---|
| v1.0 | 2026-05-19 | Initial Phase B output (A-COACH-KB-V1). 20 L3 files; 13 from existing sources + 7 NEW (03_pulling_strength, 13_tapering_redpoint, 16_assessment_interpretation, 17_readiness_overtraining, 18_equipment_fallback, 19_lifestyle_integration, 20_return_to_training). |
| v1.1 | 2026-07-19 | A237 (Adhoc Coach v0). +1 L3 file (21_adhoc_gym_sessions) for on-request commercial-gym session composition + off-plan swap trade-off. 21 L3 files total. |
| v1.2 | 2026-07-20 | C259 (KB Routing IT). Italian synonyms added to every L3 keyword row (grounding: D253 §2.2/§3.2 — IT queries matched zero rows and fell back to generic defaults). Keyword table only; no L3 content change, no new files. ASCII-only single-word terms (query tokenizer strips accents); cross-row collisions disambiguated by tie-breaker terms. `_index.md` is server-side only (parsed by `routing.py`, never injected) → zero prompt-cache impact. |
