# Coach KB v1.0 — Design Doc

**Brief ID:** A-COACH-KB-V1
**Status:** v1.0 (locked at end of Session 7b)
**Author:** Daniele Somensi
**Date:** 2026-05-26
**Supersedes:** `_archive/docs/coach_knowledge_base_spec.md` — dangling reference; never existed on disk (confirmed by audit D-COACH-AUDIT, 2026-04-29). The exercise-rationale-centric design implied by that filename is explicitly out of scope for v1.0 and deferred to v1.1 (see §7).
**Authority references:**
- `docs/research_kb/coach_kb_v1_audit.md` — Phase A audit. Source of truth for layer boundaries, file catalog (§4.6), loading strategy (§5), and governance (§6.2). The audit is the upstream specification; this design doc is its implementation contract.
- `docs/DESIGN_GOAL_MACROCICLO_v1.1.md §11` — architectural principle: the LLM Coach is a conversational layer *over* a deterministic engine. The engine is rule-based and side-effect-free; the coach reads engine state but never writes back into it.

---

## 1. Scope

This document is the implementation contract for the Coach Knowledge Base (Coach KB) — the static knowledge layer that conditions the LLM Coach's responses with project-specific evidence, voice, and safety boundaries.

In scope (v1.0):
- Layer architecture L0–L3 (file catalog, token budgets, ownership)
- Always-loaded vs routed loading strategy
- Engine-internal D-ID firewall (the 14 IDs the coach must never surface)
- Source citation policy and runtime behavior
- Governance and update cadence
- Phase progression from Phase A (audit) → Phase B (this brief) → next phases

Out of scope (deferred):
- L4 per-exercise `coach_rationale` schema and catalog wiring (deferred to v1.1; see §7)
- Coach service implementation: prompt assembly, Anthropic SDK wiring, conversation persistence, frontend chat UI (separate brief A-COACH-V1a, referenced in §6)
- Embedding/semantic routing (BM25-style keyword matching is sufficient for v1.0; see §3)

---

## 2. Architecture overview

The Coach KB is a five-layer stack. Layers L0–L2 are always loaded into the LLM system prompt; L3 is keyword-routed per request; L4 is deferred.

```
┌─────────────────────────────────────────────────────────┐
│  L0  safety_hard_rules.md      ~900 tok   always-loaded │
│  L1  coach_voice.md          ~1,200 tok   always-loaded │
│  L2  decision_index.md       ~3,000 tok   always-loaded │
├─────────────────────────────────────────────────────────┤
│  L3  20 topic files       3-7k tok each   routed (1-3)  │
├─────────────────────────────────────────────────────────┤
│  L4  per-exercise rationale     —         DEFERRED v1.1 │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
                  ┌───────────────┐
                  │  routing.py   │  ← keyword match → max 3 L3 files
                  └───────────────┘
                          │
                          ▼
                ┌─────────────────┐
                │  System prompt  │
                │  L0+L1+L2+L3*   │  ≈ 13k–32k tok worst-case
                └─────────────────┘
                          │
                          ▼
                ┌─────────────────┐
                │  Claude Sonnet  │
                └─────────────────┘
```

**Always-loaded budget:** ~5,100 tokens (L0+L1+L2). Routed L3 adds 3k–22k depending on match count.

**LLM side:** Anthropic Claude Sonnet (decision locked 2026-05-12). Provider abstraction lives in the future brief A-COACH-V1a — this design doc takes "Claude Sonnet via Anthropic SDK" as a fixed assumption and does not specify the wire format.

**Engine side:** zero coupling. The coach reads `user_state` (assessment, macrocycle, week plan, recent feedback) as read-only context. It never calls a write endpoint. Any user-confirmed action ("OK, schedule that") routes through the engine's existing REST endpoints (e.g. `/api/replanner/override`) — the coach does not patch state directly. This is the load-bearing invariant from `DESIGN_GOAL_MACROCICLO §11.1` and `§11.4`.

---

## 3. Layer specification

| Layer | File(s) | Scope | Target tok | Update cadence | Owner |
|---|---|---|---|---|---|
| L0 | `L0_safety_hard_rules.md` | 11 non-negotiable safety boundaries (D64 body-comp, D72 open-hand, D68 injury history, D80 youth <16 tool block, D81 youth <18 4-day cap, CUE-02 pre-perf stretching, etc.) | 800–1,000 | On safety-decision change (rare; requires Daniele OK) | Daniele |
| L1 | `L1_coach_voice.md` | Voice (SDT + Consuegra + Hörst), citation style, sensitive-topic protocols (body-comp, injury, eating disorders, motivation drop), CPHWA canonical format | 1,000–1,500 | On voice refinement from regression scoring or beta feedback | Daniele |
| L2 | `L2_decision_index.md` | Dense one-line decision index — 35 entries (10 safety + 25 methodological). Coach's quick-reference for "why" questions | 2,800–3,500 | On any new tagged decision in the consolidation doc | Daniele |
| L3 | `L3/01_periodization.md` … `L3/20_return_to_training.md` (20 files) | Routed topic content — see catalog table below | 3k–7k each | Per-file as evidence base evolves (new books acquired, new studies in research_kb) | Daniele |
| L4 | per-exercise `coach_rationale` JSON in `backend/catalog/exercises/v1/*.json` | DEFERRED to v1.1 | — | — | — |

### 3.1 L3 file catalog

Per audit §4.6 (v1.0 final state, 7 NEW files):

| # | File | Token (actual) | NEW? | Primary sources |
|---|---|---|---|---|
| 01 | `periodization.md` | ~6,000 | No | T03 + Hörst Ch.6 |
| 02 | `finger_strength.md` | ~7,000 | No | T04 + Hörst Ch.7 + López-Rivera + Berta |
| 03 | `pulling_strength.md` | ~3,500 | **NEW** | T01 (axis spec) + Lattice n=901 + Magiera + MacKenzie |
| 04 | `power_endurance.md` | ~4,000 | No | T05 + Hörst Ch.9 |
| 05 | `aerobic_endurance_arc.md` | ~3,500 | No | T05 + Hörst Ch.9 + CF lit |
| 06 | `technique_movement.md` | ~7,000 | No | T08 + Hörst Ch.10 |
| 07 | `mental_fear_focus.md` | ~6,000 | No | T06 + Hörst Ch.11 (gap: Ilgner not in KB) |
| 08 | `nutrition.md` | ~4,000 | No | T10 + Hörst Ch.12 §3 |
| 09 | `recovery_sleep.md` | ~4,000 | No | T07 + Hörst Ch.12 |
| 10 | `injuries_fingers.md` | ~6,000 | No | T11 + Hörst Ch.13 §1 + Schöffl |
| 11 | `injuries_shoulder_elbow.md` | ~5,000 | No | T11 + Hörst Ch.13 §2 |
| 12 | `antagonist_postural.md` | ~4,500 | No | T11 + Hörst Ch.7 §antagonist |
| 13 | `tapering_redpoint.md` | ~3,000 | **NEW** | T03 (peak phase) + Hörst Ch.6 + Mujika tapering lit |
| 14 | `female_age_youth.md` | ~4,000 | No | T12 (gap: Mobråten not in KB; Christophersen partial) |
| 15 | `goal_setting_motivation.md` | ~3,000 | No | T09 + Hardy 1996 + SDT |
| 16 | `assessment_interpretation.md` | ~4,400 | **NEW** | T01 + Lattice + Mountain Project percentiles |
| 17 | `readiness_overtraining.md` | ~4,300 | **NEW** | T07 + Meeusen 2013 + Gabbett 2016 + Hulin 2015 |
| 18 | `equipment_fallback.md` | ~4,300 | **NEW** | vocabulary_v1 §1.2 + Hörst Ch.8 home wall + synthesis |
| 19 | `lifestyle_integration.md` | ~4,200 | **NEW** | T09 + Hörst Ch.12 §5 + Watson 2017 (gap: Bechtel not in KB) |
| 20 | `return_to_training.md` | ~4,700 | **NEW** | Hörst Ch.13 §RTC + Mujika & Padilla 2000a/b + Bosquet 2013 |

**Why L4 is deferred:** Sonnet with L0+L1+L2 always loaded and 1–3 routed L3 files in context already has dense, citation-anchored grounding for every supported use case. Per-exercise rationale is a marginal improvement that adds catalog-maintenance burden across ~250 exercises. We re-evaluate after v1.0 production data shows whether users actually ask "why this specific exercise?" at a rate that justifies the wire-up cost. If yes, the L4 schema in audit §6.3 Step 7 is the implementation contract.

---

## 4. Loading strategy

Per audit §5.

**Routing trigger:** every coach turn that includes a user message. The routing module receives the user message string; the assembled system prompt includes L0+L1+L2 (always) plus up to 3 L3 files (routed).

**Routing algorithm:** see `backend/coach/routing.py` (Step 8 of this brief). BM25-style keyword counting against the routing table in `backend/coach/knowledge/_index.md`. Top-N by match count, ties broken by row order in `_index.md`, hard cap at 3 files.

**Inflection (B310).** A keyword written with a trailing `*` in `_index.md` is a **stem**, matched as a token prefix (min 4 chars). This is not cosmetic: the D265 regression scoring found **7 of 28 real Italian questions falling through to the fallback** because the index carried lemmas (`dormire`) while users type inflected forms (`dormo`) — and a query that reaches the model without its L3 file gets answered from parametric knowledge, which is how three fabricated citations entered that run. Write the stem whenever a keyword has common inflected forms, in either language (`drill*` also fixes the English plural). After B310: 1 of 28 falls back, and that one ("Ho 30 minuti oggi, cosa faccio?") correctly lands on `01_periodization` via the fallback pair.

**Cross-file co-load rule:** if a query routes to `10_injuries_fingers` AND mentions a finger-training exercise or test, additionally co-load `02_finger_strength` (within the 3-file cap). Codified in `_index.md` §"Routing rules" rule 6.

**Fallback:** zero keyword match → load `01_periodization` + `15_goal_setting_motivation` as generic defaults. Documented in `_index.md` rule 5; replicated in `routing.py`.

**Token budget envelope** (per audit §5):

| Scenario | Always | L3 | Engine state | Total input |
|---|---|---|---|---|
| Typical 1-file | 5.1k | ~5k | ~3k | ~13k |
| Cross-domain 2-file | 5.1k | ~10k | ~3k | ~18k |
| Worst-case 3-file | 5.1k | ~22k | ~5k | ~32k |

Output target: 300–800 tokens per coach response. Sonnet's 200k context window leaves substantial headroom — token budget is a cost concern, not a feasibility one. Prompt caching (Anthropic feature) on L0+L1+L2 amortises the ~5.1k always-loaded prefix across turns.

---

## 5. Engine-internal firewall

Fourteen decision IDs are tagged `⚙️ engine_internal` in the decision consolidation. The coach must **never** surface these to the user, cite them, or reason from them. They describe scheduling cadence, protocol selection, internal hyperparameters, and other engine implementation details that have no user-facing decision surface.

**The 14 forbidden D-IDs:**

```
D03  D04  D05  D06  D08  D13  D23  D32  D42  D61  D62  D63  D88  D90
```

**Where they're documented:** every L3 file that overlaps a firewalled domain includes an explicit firewall acknowledgement. Notable cases:
- `L3/02_finger_strength.md` — names D88 (test scheduling cadence) and D90 (test_max_hang protocol selection) inside a firewall block to make the boundary explicit
- `L3/16_assessment_interpretation.md` — same firewall block for D88/D90: "the coach reads test outputs but does not reference the scheduling/protocol-selection layer; the engine has already done that work by the time a user asks 'what does my score mean?'"

**Enforcement (v1.0 — manual):**
- L3 file authoring: grep regex `\bD(03|04|05|06|08|13|23|32|42|61|62|63|88|90)\b` against each L3 file before commit. The only acceptable match is a documented firewall block (not a citation).
- Regression set §6.1 includes Q-17 and Q-24 probing for engine-internal hallucination. Hard-fail if the coach surfaces a firewalled ID.

**Enforcement (v1.1 — proposed):** add the grep regex to a CI check or pre-commit hook that scans `backend/coach/knowledge/` and fails on any non-firewall-block match. Tracked as v1.1 open item.

**Rationale:** the coach is a conversational layer over the engine, not a window into the engine's implementation. Surfacing scheduling cadence ("the engine schedules MVC-7 every 6 weeks") tempts users to second-guess deterministic logic that exists precisely to remove that decision from the user. The same logic applies to protocol-selection heuristics and internal hyperparameters.

---

## 6. Source citation policy

**Format:** `Author Year` inline. No DOIs, no academic parentheticals, no effect sizes or CIs unless directly load-bearing for the answer.

✅ `Per Watts 2000, easy traversing clears lactate ~35% faster than sitting between attempts.`
❌ `Williams et al. (2017) demonstrated (ES = 0.43; 95% CI 0.27-0.58)…`
❌ `Studies show…` (unverifiable)

**When to cite:** L1 §3 default — the coach mentions sources only when (a) the user asks "why" or "source?" or (b) the recommendation is non-obvious and counter-intuitive. Citations are not on by default — they're available on request. This is the runtime policy locked 2026-05-12.

**No fabrication rule:** if a source is not in L2/L3, the coach says so: *"I don't have a specific source for that — want me to flag it for research?"* Inventing a citation is a hard L1 violation.

**Contested evidence signalling:** when the evidence base is unsettled (Abrahangs, lifting-edge protocols, Critical Force, menstrual-phase prescription), the coach prefixes with uncertainty: *"there's a recent study suggesting X — not conclusive yet, but worth knowing."* Confident in evidence, humble in inference (L1 §2).

### 6.1 Gap markers and the v1.1 refresh queue

Several L3 files carry explicit `v1.0 coverage gap` blocks naming sources we know we should distill but haven't yet acquired or read deeply. These are the visible debt items the regression scoring will tolerate:

| Source | Affected L3 files | Status |
|---|---|---|
| Bechtel — "Integrated Strength Training" pp.31-90 | 06, 19 | Not photographed yet |
| MacLeod — "9 Out of 10 Climbers" 2nd ed. | 07, 15 | Not in KB |
| Ilgner — "The Rock Warrior's Way" | 07 | Not in KB |
| Mobråten & Hagen — "The Climbing Bible" | 14 | Not in KB |
| Christophersen — "Climbing Injuries Solved" | 10, 11, 14 | Partial (audit summary only) |
| Mujika & Padilla 2000a/b — detraining primaries | 20 | Synthesised from secondary; primaries not distilled |
| Lattice 2024 — lifting-edge / MXEdge shift (~30% of plans) | 02, 18 | Mentioned as gap; not protocol-distilled |

These gaps are acceptable for v1.0 — every affected file has the gap block explicit so users (and future Daniele) can see the boundary. v1.1 refreshes the affected files once the sources land in `docs/research_kb/`.

---

## 7. Phase progression

### Phase A — KB audit and tagging (closed 2026-05-19)

Brief: D-COACH-AUDIT. Output: `docs/research_kb/coach_kb_v1_audit.md` (1066 lines, 40k tok). Identified 5 surface-level decisions for the coach, 35 decisions worth indexing, 14 engine-internal to firewall, and a 20-file L3 catalog with token targets, source attribution, and routing keywords.

### Phase B — Content layer (this brief, A-COACH-KB-V1)

10 steps per audit §6.3. Sessions 1–7b:

| Session | Date | Steps closed | Output |
|---|---|---|---|
| 1 | 2026-05-19 | 1, 2 | Scaffold + L0 |
| 2 | 2026-05-19 | 3, 4 | L1 + L2 |
| 3 | 2026-05-20 | 5 (Batch A) | L3 files 01-05 (1 NEW: 03) |
| 4 | 2026-05-21 | 5 (Batch B) | L3 files 06-09 |
| 5 | 2026-05-22 | 5 (Batch C+D) | L3 files 10-15 (1 NEW: 13) |
| 6 | 2026-05-23 | 5 (Batch E) | L3 files 16-20 (5 NEW) — **Step 5 closed** |
| 7a | 2026-05-26 | 6, 8 | This design doc + `routing.py` + unit tests |
| 7b | TBD with Daniele | 9, 10 | Regression scoring + v1.0 lock |

Step 7 (L4 schema + 30-exercise rationale wiring) is **deferred to v1.1** by Daniele's scope decision — see §3 last paragraph.

### Next phase — Coach service implementation (A-COACH-V1a, future brief)

Out of scope here. Wires the Coach KB into a runtime service:
- Prompt assembly: L0+L1+L2 + routed L3 + engine context (user_state slice + recent feedback) → Anthropic Messages API
- `POST /api/coach/chat` endpoint with conversation history
- Provider abstraction (so Sonnet can be swapped if cost or capability changes)
- Frontend chat UI on a new `/coach` route
- Conversation persistence (Supabase JSONB)

A-COACH-V1a depends on Coach KB v1.0 being locked (end of Session 7b).

---

## 8. Governance

Per audit §6.2 (verbatim alignment required).

**Source of truth.** `docs/research_kb/coach_kb_v1_audit.md` is the upstream specification. Any change to layer boundaries, the firewall list, the 20-file catalog, or the loading strategy must update the audit first, then propagate to this design doc, then propagate to the affected `backend/coach/knowledge/` files. Updating the implementation without updating the audit is a governance violation.

**Change cadence.**
- **Patch changes** (typo, citation fix, single-paragraph clarification): direct commit, no review needed, sync_status as usual.
- **Minor changes** (add/remove an L3 file, expand a section, refresh a gap source): brief required, regression scoring re-run on affected use cases.
- **Major changes** (new layer, change firewall list, change loading strategy, change voice principles): full audit revision + brief + full 28-question regression.

**Decision authority.** Daniele approves all major and minor changes. Patch changes proceed in autonomous mode.

**Versioning.** Coach KB versions semver-style. v1.0 locks at end of Session 7b. v1.1 ships when the first deferred gap (Bechtel, MacLeod, etc.) is integrated, or when L4 wiring goes in — whichever lands first.

**Regression discipline.** The 28-question regression set in audit §6.1 is the contract. Any change that could affect coach output must re-run the affected questions and score ≥80%. Hard-fail questions (Q-13, Q-14, Q-22, Q-26, Q-27, Q-28) probe safety boundaries and engine-internal firewall — any breach blocks the change.

---

## 9. Open items for v1.1

1. **L4 wiring decision.** Re-evaluate after v1.0 production data. If user transcripts show repeated "why this exercise?" questions that L0+L1+L2+L3 don't answer adequately, implement the L4 schema per audit §6.3 Step 7. Initial scope: 30 most-prescribed exercises.

2. **Token-undershoot refresh.** Several L3 files landed 13–25% under target (notably the Batch B/C files where the underlying source extraction was already dense). Decision pending: accept as-is, or refresh with additional synthesis when the gap sources (Bechtel, MacLeod, etc.) arrive. Default: accept; refresh only on actual content gap surfaced by regression scoring or beta feedback.

3. **Firewall CI enforcement.** Add the engine-internal D-ID grep regex (`\bD(03|04|05|06|08|13|23|32|42|61|62|63|88|90)\b`) to a CI check that scans `backend/coach/knowledge/` and fails on any non-firewall-block match. Currently enforced manually at commit time.

4. **Source acquisition.** Books still to acquire and distill for v1.1: Bechtel ISG pp.31-90 (files 06, 19), MacLeod 9OoT 2nd ed. (07, 15), Ilgner RWW (07), Mobråten & Hagen Climbing Bible (14). Christophersen needs deeper extraction (currently audit-summary only).

5. **Lattice 2024 lifting-edge / MXEdge protocol.** Mentioned as a gap in files 02 and 18. Lattice reports ~30% of their plans now use this approach; the protocol details are not yet in the KB. v1.1 task: distill from Lattice public sources and integrate as a protocol variant in `02_finger_strength.md`.

6. **Routing upgrade — embeddings.** v1.0 uses BM25 keyword matching plus stems (B310). If beta data shows >10% of queries fall through to the fallback (no keyword match), upgrade to a small embedding model (e.g. `text-embedding-3-small` or open-weights equivalent) with cosine similarity against per-file summaries. Out of scope for v1.0; threshold-triggered.

7. **Provider abstraction.** When A-COACH-V1a ships, wrap the LLM call in a provider interface so Sonnet can be swapped without touching prompt-assembly logic. Not a KB concern, but listed here because the KB design assumes a Sonnet-class context window — if a smaller model becomes the target, the always-loaded budget needs to drop.
