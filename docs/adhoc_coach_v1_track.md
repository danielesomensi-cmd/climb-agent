# Adhoc Coach v1 — Implementation Track (brief)

> **Status:** DRAFT brief, ready to execute after v0 (A237) field validation.
> **Type:** A (feature), **multi-phase track**. Touches high-risk boundaries → each phase is **analysis-first with a mandatory STOP** (CLAUDE.md protocol).
> **Model:** suggest Opus for each phase's Phase-0 analysis (touches `custom_session` insertion, per-exercise logging → `working_loads`, closed-loop boundary, load accounting). Sonnet OK for mechanical implementation after each STOP.
> **Predecessors:** [[D252]] (foundation audit), A237 (Adhoc Coach v0 — conversational composition, shipped 2026-07-19), C258 (commercial-gym exercise batch).

## Phase 0 — Brief ID

Each of the 3 phases below is a **separate brief**. Run `python scripts/next_brief.py` at the start of each and take the returned A-number. Do NOT pre-assign numbers.

## Context & goal

v0 (A237) proved the coach can compose a credible commercial-gym session in chat (text only). v1 turns that into a **real, runnable, logged session** — a proper session object with timers, per-exercise logging, and load locking — that is **strictly additive** (never modifies planned/past sessions) and counts in weekly load.

**Foundation decision (from Part-1 assessment + D252): build on `custom_session`, do NOT invent a new object type.** The insertion path (`add_custom_session` replanner event) is already additive and immutability-safe (D252 §C.5), and custom-session load already reaches all 4 reporting surfaces, locked at add-time (D252 §B). What's missing are the three gaps D252 found — and those are exactly the v1 prerequisites:

| D252 finding | Severity | Blocks v1 because |
|---|---|---|
| Custom player sends only `mark_done`; no per-exercise load/RPE/duration logged | **HIGH (C.4)** | An adhoc "session I actually did" that logs nothing is pointless; also can't feed load history |
| No `working_loads` read or write in the custom path | **HIGH (C.2)** | Re-picking an exercise can't remember last load → coach/builder can't learn |
| Builder proposes no load (`load_kg` default 0) | **MED (C.3)** | Composed RPE targets don't carry into the runnable session |
| No immutability test on custom insert | **MED (C.5)** | Must be guarded before we add a second writer of adhoc sessions |

So v1 = close those gaps, then wire the coach→builder bridge. Three sequenced phases.

---

## Phase 1 — Custom-session per-exercise logging + immutability guard (foundation)

**Closes D252 C.4 (HIGH) + C.5 (MED). Mixed backend + frontend → `brief/` branch + Vercel preview (B196).**

Scope:
- The custom-session player (`session-builder/[id]/play/page.tsx`) captures, per exercise: **used load (RPE and/or kg if the user enters it), sets completed, and duration**, and on finish persists a real per-exercise log — reuse the existing `exercise_feedback_v1` shape the guided player already writes (`guided/[date]/[sessionId]/page.tsx:330-438`), don't invent a new schema.
- Backend: accept and store that log for `is_custom` sessions. **STOP-GATE ANALYSIS REQUIRED**: this touches the feedback path and the closed-loop boundary — adhoc/custom sessions must **write `working_loads` but NOT feed closed-loop progression** (they are off-plan support work; confirm the existing `is_custom` guards at `replanner_v1.py:1212` and the frontend guards at `week/page.tsx:412` / `today/page.tsx:470` stay intact). List every call site before touching `feedback.py` / `closed_loop_v1.py`.
- Add the missing immutability test (D252 C.5): assert a custom insert/complete never mutates a sibling/past session's `exercise_id`/loads/status.

**Non-negotiable:** past-session immutability (CLAUDE.md). Load stays locked at completion (as today).

DoD: per-exercise logging works end-to-end through the custom player; `working_loads` updated on finish; closed-loop NOT triggered by adhoc; immutability test green; full suite green; preview approved.

## Phase 2 — Load proposal + history in the builder

**Closes D252 C.2 (HIGH) + C.3 (MED). Backend-focused (+ minor builder UI).**

Scope:
- When an exercise is picked (in the builder or by the adhoc composer), propose a starting prescription: derive from the exercise's `prescription_defaults` + current macrocycle phase, and **overlay the user's last logged `working_loads`** for that exercise when present. Output as **RPE/RIR primary; kg only as a remembered value the user previously logged** — never an invented absolute.
- Surface "last time: X" when re-picking (reads the history Phase 1 now writes).

**STOP-GATE ANALYSIS**: proposal logic must stay deterministic and must not leak into planned-session resolution (`resolve_session` untouched — this is custom-only).

DoD: builder/preview shows a sensible per-exercise RPE proposal + last-logged value; no absolute-kg invention; deterministic; suite green.

## Phase 3 — Coach → deterministic adhoc builder bridge (the feature)

**The actual "adhoc coach session". Backend + frontend → branch + preview.**

Scope:
- New deterministic module `adhoc_builder` (sibling of `custom_session.py`, **not** in the coach): given a structured intent `{equipment_set, focus, minutes, energy, phase, harmonization_context}`, it picks exercises from the catalog (equipment/domain/phase/spine-safe filters, reusing C258 commercial-gym coverage) and returns a `custom_session` object, flagged `adhoc: true`.
- The **LLM only extracts the structured intent** (a small JSON slot-spec) from the chat turn — it never picks exercises or loads. Deterministic engine composes. This preserves the "deterministic engine" product claim.
- The composed session is inserted **additively** via the existing `add_custom_session` event (slot-conflict guarded, no replanner ripple), runnable via the Phase-1 player, logged, load-locked, counted in weekly load.
- Coach presents + explains the composed session and offers to save/run it.

**STOP-GATE ANALYSIS**: touches the `add_custom_session` insertion path and the coach service. Confirm: no modification to `planner_v2`/`replanner_v1` logic (reuse only), no touch to `resolve_session` P0 filters, immutability preserved, load accounting unchanged (custom load already flows to all 4 surfaces).

DoD: end-to-end — chat intent → deterministic composed session → inserted additively → run with timers → logged → counted in weekly load; planned sessions provably untouched; suite green incl. a new adhoc-builder determinism test + insertion-immutability test; preview approved.

---

## Non-goals (hard, whole track)

- **Scenario 2 "swap the planned session"** (actually replacing a planned session) stays **out** — remains suggest-only in the coach. v1 is strictly **additive**.
- No absolute-kg prescriptions the engine invents (RPE/RIR primary; kg only as user-logged memory).
- No new subscription/endpoint sprawl beyond what each phase needs; reuse `custom-session` plumbing.
- No touching `resolve_session` P0 filters, `planner_v2`, `macrocycle_v1`, or `progression_v1`.
- BUG-2 (language enforcement) stays out of scope.

## Sequencing rule

Ship **Phase 1 → 2 → 3 in order** (each merged + verified before the next). Phase 3 is worthless without Phase 1's logging; Phase 2 makes Phase 3's output usable. Do not start Phase 3 before 1 & 2 are on main.

## Open questions to resolve during field validation of v0

- From the gym test of v0: does the coach's composed session quality hold across phases (base vs power-endurance emphasis)? Any exercise the menu is missing? Fold findings back here before starting Phase 1.
- Confirm whether adhoc sessions should be visibly distinguished from custom sessions in the UI (badge), or treated identically once inserted.
