# C265 — Catalog language sweep + handstand kick-up content fix

**Type:** C (catalog/content) · **Date:** 2026-08-01 · **Scope:** backend-only, content JSON + one test constant.

Trigger: a production screenshot of the guided player (adhoc session "Primer pre-Berdorf")
showing *Handstand Kick-up (a Muro)* rendered in Italian inside an all-English UI.

---

## 1. Method — how the inventory was built

Three independent sweeps over **every** JSON under the repo (discovered with `rglob`, not a
hardcoded file list, so a package nobody remembers is still covered):

1. **Token sweep** — Italian function words + domain vocabulary, restricted to user-facing keys.
2. **Morphological sweep** — Italian-only suffixes (`-zione`, `-mento`, `-ità`), accented
   characters and elided articles (`l'`, `dell'`), with common English `-tion`/`-ment` words
   subtracted first so they don't drown the signal.
3. **Inverse sweep** — long strings containing **no** English function word at all. This one is
   noisy by design (video URLs, telegraphic notes) but it is the only one that would catch
   Italian written without any of the tokens the first two look for. It found one extra field
   the first sweep missed — `benchmark_note`, whose key was not in the user-facing list.

Running three sweeps was not redundancy for its own sake: sweep 1 missed a field sweep 3 caught,
and sweep 2 was the only one to flag the Latin quotes' Italian glosses.

## 2. Inventory found (all fixed)

| File | Entry / path | Fields |
|---|---|---|
| `exercises/v1/exercises.json` | `frog_stand` | description, 5 cues, notes |
| | `handstand_kick_up_wall` | **name**, description, 5 cues, notes |
| | `heel_pulls_chest_to_wall` | **name**, description, 5 cues, notes |
| | `wall_handstand_shrugs` | **name**, description, 4 cues, notes |
| | `test_max_hang_duration_20mm` | benchmark_note |
| | `test_l_sit_hold` | benchmarks.source, 3 labels, scale note |
| | `test_max_pullup_bw` | description |
| `sessions/v1/boulder_circuit_gym.json` | `modules[2]` | notes ×2 |
| `sessions/v1/finger_maintenance_home.json` | `modules[2]` | notes ×2 |
| `sessions/v1/finger_strength_home.json` | `modules[2]` | notes ×2 |
| `sessions/v1/power_endurance_gym.json` | `modules[4]` | notes ×2 |
| `quotes/v1/quotes_catalog_v1.json` | q118, q125, q126, q147 | 2 authors, 2 Italian glosses of Latin quotes |

**Provenance correction:** the brief guessed the handstand package was authored in Feb 2026. It
was not — the four Italian entries come from **D262 (2026-07-29)**, five days before the
screenshot. The other suspect packages named in the brief (yoga/mobility, general conditioning:
TGU, farmer's carry, bear crawl, jump rope) are clean English; the sweeps found nothing there.
Templates, mobility, milestones, daily tips, free-session presets and outdoor strategy/nutrition
are clean too. **The exposure was 3 files, not an era.**

`test_l_sit_hold`'s benchmark labels were the one item with a code consumer:
`test_session_1b.py::test_benchmarks_labels` asserted the Italian strings. That assertion is a
data assertion, not a behaviour one — updated in the same commit.

## 3. The kick-up: what was actually wrong

The brief reported the entry as an unexecutable merge of two drills — chest-to-wall toe pulls
plus a kick-up. **The catalog never contained that merged text.** The string quoted in the brief
("Dal chest-to-wall stacca un piede… Poi slancio controllato") does not exist anywhere in the
repo. What the entry did contain was a coherent-but-Italian kick-up description, sitting one card
away from `heel_pulls_chest_to_wall`, which is the chest-to-wall drill. The two read as one
muddled exercise on screen.

That does not make the finding wrong, only differently located: the entry was still under-specified
in the way that produced the confusion. *"fermandosi al muro"* never said **which side** faces the
wall, and a kick-up that stops at the wall is ambiguous exactly where a chest-to-wall drill would
differ. The rewrite states it: **back to the wall**, heels arriving against it, the wall as a brake
rather than a target, plus an explicit cross-reference to the chest-to-wall drill by name.

**Decision on the chest-to-wall content:** dropped from this entry, no new catalog entry created.
`heel_pulls_chest_to_wall` already covers that drill in full (own id, own recency group
`handstand_freestanding`, own prescription) — a second entry would be a duplicate competing with it
in the same selection pools. The progression now reads cleanly across its steps:
`frog_stand` → `wall_walk_up` / `handstand_kick_up_wall` (entries) → `wall_handstand_hold` /
`wall_handstand_shrugs` / `handstand_shoulder_taps` (holds) → `heel_pulls_chest_to_wall` →
`freestanding_handstand_practice`.

## 4. Guard test — kept

`backend/tests/test_c265_catalog_language.py` (3 cases: one sweep over every live catalog file,
plus two self-checks). Design decisions, since the brief left the call open:

- **Italian function words are the primary signal.** Articles and prepositions are unavoidable in
  Italian prose and essentially absent from English. Domain nouns alone would be weaker — one
  "muro" could be a proper noun in an otherwise English string.
- **Accented characters are deliberately NOT flagged.** Legitimate content carries them in proper
  nouns (Eva López, Antoine de Saint-Exupéry, Hörst); that rule would need a whitelist growing with
  every author cited, for no detection gain over the function-word rule.
- **Ambiguous tokens are excluded by construction** — `per`, `come`, `tempo`, `via`, `in`, `a`, `e`,
  and `non` (which appears in "non-negotiable", "non-working"). A guard whose failures are usually
  false teaches everyone to ignore it.
- The detector is **anchored on a real pre-C265 string**, and a second test asserts it stays quiet
  on the English strings that tripped the drafting heuristics — [[B317]]'s lesson: a test written
  against invented data verifies the function, not the world.
- **Not parametrised per file, and `_archive/` excluded.** The first draft was one case per catalog
  file, which looked tidier and was wrong: the file list comes from the filesystem, `_archive/` is
  gitignored, so the collected test count differed between a fresh clone (64 files) and this
  machine (85) — and `sync_status.py` writes that count into `PROJECT_BRIEF.md` and `README.md`,
  where the pre-push hook then compares it. A counter that depends on which machine ran it is worse
  than no counter. Caught by the sync step reporting 3111 against a suite that had just printed
  3090.

## 5. Guardrails verified

- **Exercise ids unchanged** — diffed against `origin/main`: 259 ids, identical in value *and*
  order. Only text fields differ; every non-text field is byte-identical across all 259 entries.
- **Past sessions untouched** — `resolve_session` copies `name`/`cues` into the resolved session at
  resolution time (`resolve_session.py:1207`), so already-persisted sessions keep the text they were
  resolved with. Nothing here triggers regeneration; catalog text is read at render time for new
  resolutions only. Full suite green, including the immutability tests.
- No high-risk module touched. No schema change. No grade text involved.

## 6. Verification

- Backend suite: **3027 passed** (3024 + 3 new), 41 subtests.
- Guard verified by injecting Italian into a live session file and watching the sweep fail with the
  offending file, path and words named — then restoring it. A guard is only worth its line count if
  you have seen it fail on the real path, not just on its own unit self-check.
- Smoke: `compose_adhoc_session(focus="handstand")` composes 8 exercises with the corrected English
  names and unchanged ids; `handstand_practice` resolves `success`.
- All three sweeps re-run post-fix: zero Italian remaining. Residual hits are false positives
  ("non-negotiable", "non-working") and one French proper noun.
