# D235 — Project Description Rationalization

> **Type:** D (audit + drafting, read-only)
> **Date:** 2026-05-09
> **Author:** Daniele Somensi
> **Status:** Draft for review

---

## 0. Context

The claude.ai project description currently dates from **2026-03-07** and has drifted ~2 months out of sync with the codebase. The drift is caused by a structural mismatch:

- **Mounted files** (`PROJECT_BRIEF.md`, `CLAUDE.md`, `README.md`) are refreshed daily via `python scripts/sync_status.py` + commit hook.
- **Project description** is plain text edited manually in claude.ai settings — there is no automated sync path.

Single corrective rule encoded in the new draft: **if chat instructions conflict with mounted files, mounted files win.** Combined with stripping every dynamic line from the description, this prevents future drift by construction.

---

## 1. Classification table (Phase 1)

Walked the current claude.ai project description from `## Project` through `## Communication style`. Every section is classified `STABLE` (keep), `DYNAMIC` (delete, lives in mounted file), or `REDUNDANT` (delete, already in CLAUDE.md or README).

| Section / line | Bucket | Rationale | Covered by |
|---|---|---|---|
| `## Project` — "deterministic engine, no LLM at runtime, Hörst 4-3-2-1 + DUP, lead+boulder" | STABLE (high-level def) | One-line product identity. Doesn't change unless methodology changes. | Stays in description. Also in `CLAUDE.md` §"What climb-agent is". |
| `## Project` — "Author: Daniele **Somensi** (with an S, not Z)" | STABLE | Identity, never changes. | Stays in description. Also in `CLAUDE.md` line 7. |
| `## Project` — "Core question: Given my goal, my weaknesses, my time, what should I train today?" | STABLE | Product framing. | Stays. Also in `PROJECT_BRIEF.md` line 12. |
| `## Your role` — "senior software engineer, meticulous, two steps ahead, edge cases" | STABLE | Role definition. | Stays. Also in `CLAUDE.md` line 5 (overlapping wording). |
| `## Your role` — "paid production within weeks. Every decision through that lens" | DYNAMIC | Already happened — Stripe LIVE since 2026-04-16. Phrase implies pre-launch. | Drop. Replace with neutral "production-grade quality" framing. |
| `## How we work` — chat ↔ Claude Code split | STABLE | Workflow rule. | Stays in description. Not duplicated in CLAUDE.md (CLAUDE.md is read by Claude Code itself, not by this chat). |
| `## How we work` — Brief types A/B/C/D | STABLE | Vocabulary that both ends use. | Stays in description (one-liner each). Brief content lives in chat-specific roadmap. Definitions also implicit in `CLAUDE.md` line ~225 ("A = new feature, B = bugfix, C = catalog/content, D = audit/documentation"). |
| `## How we work` — "analyze first, wait for OK before implementing" | STABLE | Brief principle. | Stays in description. Reinforced operationally by `CLAUDE.md` §"Execution model" / "When you MUST stop". |
| `## How we work` — "offer to prepare a brief at every task definition" | STABLE | Behavioral rule for this chat. | Stays. |
| `## Current status (as of 2026-03-07)` — entire section | DYNAMIC | All numbers wrong. **758→1984 tests, 153→218 exercises, 29→35 sessions, 23→19 templates, 38→68 endpoints, 25→42 pages, 44→76 components, 14 routers→19 routers**. "Backend Python/FastAPI on Railway" wording OK but already in CLAUDE.md. "Frontend Next.js 14" wrong (now 16). "Persistence: JSON files... Supabase planned" wrong (Supabase live). "Multi-user: UUID + X-User-ID. Clerk planned" wrong (Clerk live). Recovery codes still relevant but covered. | `PROJECT_BRIEF.md` (counters, persistence, auth) + `CLAUDE.md` §"Deployment" + §"Auth". Drop entirely. |
| `## Architecture` (diagram) | DYNAMIC + REDUNDANT | "Macrocycle 10-13 weeks" stale (now caps at 16, A218). Diagram already in `CLAUDE.md` §"Engine architecture" and `PROJECT_BRIEF.md` §"Architecture". | Drop. |
| `## Architecture` — module names | REDUNDANT | "assessment_v1, macrocycle_v1, planner_v2, replanner_v1, resolve_session, progression_v1, closed_loop_v1" — same list in `CLAUDE.md` §"Engine architecture" → "Key modules". | Drop. |
| `## Repo structure` (tree) | REDUNDANT | Same tree (longer, more accurate) in `CLAUDE.md` §"Repository structure" and `README.md` §"Repository layout". | Drop. |
| `## Documentation architecture` | REDUNDANT | Same list in `CLAUDE.md` §"Documentation architecture". Reference to `audit_location_equipment.md` is stale (file relevant to ARCH-1 era). | Drop. |
| `## Go-to-market priorities (next ~2 weeks)` | DYNAMIC | All 4 items obsolete: P1 bug list (B37/38/42/48/UI-9/UI-25/FR-4) all closed long ago, P2 (Auth+Payments+DB) all done, P3/P4 reshaped multiple times. | `docs/ROADMAP_CURRENT.md` is the live source. Drop. |
| `## Future phases` | REDUNDANT | LLM Coach phase 3.5 covered in `docs/ROADMAP_CURRENT.md` §"Future — Phase 3.5: LLM Coach". Phase 4+ items also in roadmap. | Drop. |
| `## Non-negotiable principles` | STABLE (concept) but list **mismatches** CLAUDE.md | Chat description lists 6 (determinism, single source of truth, append-only logs, official maxes, closed vocabulary, P0 filters). CLAUDE.md lists 7 (deterministic, closed-loop, data-driven, test-first, past sessions immutable, Fontainebleau, equipment-based filtering). Two different lists → drift hazard. | Replace with **single line referring to CLAUDE.md** as authoritative. Don't duplicate. |
| `## Key technical context` — equipment-based filtering | REDUNDANT | Identical rule in `CLAUDE.md` line 21. | Drop. |
| `## Key technical context` — gym lookup uses `name` field | DYNAMIC (engine impl detail) | Not in `CLAUDE.md`. Implementation reality, may evolve. | **GAP** — see §3. |
| `## Key technical context` — planner iterates all gyms | DYNAMIC (engine impl detail) | Not in `CLAUDE.md`. | **GAP** — see §3. |
| `## Key technical context` — iOS PWA quirks (AudioContext, wall-clock timers, localStorage UUIDs) | DYNAMIC | Not in `CLAUDE.md`. Important for any frontend brief touching audio/timers/auth. | **GAP** — see §3. |
| `## Key technical context` — Railway filesystem ephemeral | REDUNDANT | Covered indirectly by `CLAUDE.md` §"Environment variables" → `DATA_DIR` and `STORAGE_BACKEND` rows. | Drop. |
| `## Key technical context` — Grading Fontainebleau | REDUNDANT | Verbatim in `CLAUDE.md` line 20. | Drop. |
| `## Key technical context` — Training literature (Hörst, Lattice, Eva López, Tyler Nelson, Hooper's Beta) | DYNAMIC | Not listed by name in CLAUDE.md, but `docs/literature_review_climbing_training.md`, `docs/docs_literature_hangboard.md`, the KB project, and ROADMAP refs (Bechtel, MacLeod, Ilgner, Mobråten, Christophersen) cover authors much more thoroughly. | Drop — bibliography is in those files. |
| `## Communication style` — Italian, direct, profanity tolerated, prefers short prompts, ask clarifying questions | STABLE | User-behavior memo specific to this chat. Has no place in CLAUDE.md (which is for Claude Code, not for this chat). | Stays in description. |

**Summary:** ~85% of the current description is DYNAMIC or REDUNDANT. The new draft keeps only ~15% (role, workflow, vocabulary, communication style) and adds the source-of-truth rule.

---

## 2. New project description (Phase 2)

Ready to copy-paste into claude.ai → Settings → Project → Description. **52 lines**, zero numeric counters, zero deployment URLs, zero "planned/WIP" markers.

```markdown
## climb-agent

A deterministic climbing training engine. Generates personalised weekly plans, resolves abstract sessions into concrete exercises with sets/reps/load, and adapts through closed-loop feedback. No LLM is used at runtime — all logic is rule-based and testable. Methodology: Hörst 4-3-2-1 adaptive periodization with DUP. Supports both lead and boulder.

Core question: **"Given my goal, my weaknesses, and my available time, what should I train today?"**

Author: Daniele **Somensi** (with an S, not Z).

## Roles

- **This chat (claude.ai)** = strategy, planning, brief preparation, review, post-mortems.
- **Claude Code (Mac terminal)** = implementation, file edits, tests, commits, pushes. Operates with `--dangerously-skip-permissions`; safety enforced through brief structure and STOP gates.

You are a senior software engineer and product strategist. Meticulous, detail-oriented, two steps ahead. You care about edge cases, test coverage, UX, and production-grade quality.

## Language rule

All chat communication with Daniele is in **Italian**. All technical artifacts (code, commit messages, briefs, docs, comments) are in **English**. Both rules are non-negotiable.

## Brief types

When defining a task, **always offer to prepare a structured brief** for Claude Code. Four types:

- **A** — new feature
- **B** — bug fix
- **C** — catalog / content expansion
- **D** — audit / documentation (read-only)

Briefs follow "analyze first, wait for OK before implementing". Numbered sequentially across all types — Claude Code runs `python scripts/next_brief.py` to assign the next number.

## Source of truth

Live status, architecture, conventions, and open work all live in **mounted files**, not in this description:

- **`PROJECT_BRIEF.md`** — current counters (tests, exercises, sessions, endpoints, pages, components), persistence and pricing snapshot. Auto-updated by `scripts/sync_status.py`.
- **`CLAUDE.md`** — engineering conventions, commands, repo structure, engine architecture, full endpoint table, deployment, environment variables, branch workflow, non-negotiable principles, lessons-learned protocol.
- **`docs/ROADMAP_CURRENT.md`** — every open item, current priorities, P1/P2/P3 buckets, recently closed.
- **`docs/vocabulary_v1.md`** — closed domain vocabulary (enums, schemas).

**Rule: if anything in this description contradicts a mounted file, the mounted file wins.** This description must never carry numeric counts, version strings, deployment URLs, env var names, current-week priorities, or status markers ("planned", "WIP", "live") — those drift in days. Refer to mounted files instead.

For non-negotiable engineering principles (determinism, closed-loop, data-driven, test-first, past sessions immutable, Fontainebleau for boulder grades, equipment-based filtering), defer to `CLAUDE.md` §"Non-negotiable principles" — that list is canonical.

## Workflow

- Always offer to prepare a brief at every task definition.
- Ask clarifying questions before answering when the task is ambiguous.
- When something cannot be derived from mounted files (e.g. business intent, beta-tester feedback, design rationale), Daniele provides it in chat.
- Daniele uses profanity when frustrated — it's signal, not a problem. Prefer short, ready-to-paste prompts over long explanations.
```

**Line count:** 52 (within ≤60 target).
**Counters:** 0.
**URLs:** 0.
**"planned" / "WIP" markers:** 0.

---

## 3. Gap table (Phase 3) — verified

Each row in the candidate gap list was verified by targeted grep against the mounted files. Verification commands run: `grep -rn` on `CLAUDE.md`, `docs/vocabulary_v1.md`, `docs/ENGINE_ARCHITECTURE.md`, `docs/ROADMAP_CURRENT.md`, `docs/lessons.md`, `docs/audit/*`, `PROJECT_BRIEF.md`.

`verified_status` legend:
- **TRUE_GAP** — confirmed absent from every mounted file. Net new content needed.
- **PARTIAL** — present somewhere but scattered or incomplete. Consolidation recommended.
- **DUBIOUS_CLAIM** — the claim itself contradicts evidence in mounted files; needs to be re-verified against actual code/schema before being added anywhere.
- **ALREADY_PRESENT** — fully covered. Drop the row, no action.

| Removed item | Should live in | verified_status | Evidence | Action for follow-up |
|---|---|---|---|---|
| Gym lookup uses `name` field (no `gym_id` in `user_state.gyms`) | `CLAUDE.md` | **DUBIOUS_CLAIM** | `vocabulary_v1.md:21` "context.gym_id (required when location='gym')", `:169` "context.gym_id: string (required)", `:173` "If location='gym', gym_id MUST be present", `:1140` "gym requires gym_id". `ENGINE_ARCHITECTURE.md:44/275/336/510/525/744` consistently uses `gym_id` in week_plan dict, slot dicts, context, and `apply_day_override(gym_id=...)` signature. Example payload at line 744: `"gym_id": "palestra_1"`. The claim that "user_state.gyms entries have no gym_id" contradicts this. **Likely the claim is stale or refers to a narrower scope (e.g. how `user_state.gyms` is keyed vs. how plans reference gyms).** | **DO NOT add to CLAUDE.md.** Verify against actual `user_state` schema and `planner_v2.py` gym-resolution code first. If the claim is real, file a B-brief — it's a code-vs-doc mismatch, not a doc gap. |
| Planner iterates **all** gyms, not only the priority-1 gym | `CLAUDE.md` | **TRUE_GAP** | Zero hits in `CLAUDE.md` and `ENGINE_ARCHITECTURE.md` for "iterate all gyms", "priority-1", "priority gym". | Add one bullet to `CLAUDE.md` §"Engine architecture" → "Key modules" under `planner_v2.py`. **Eligible for C237 follow-up.** |
| iOS PWA quirks: AudioContext requires user gesture; timers must use wall-clock; localStorage UUIDs can be lost on reinstall | `CLAUDE.md` (consolidated) | **PARTIAL** | Wall-clock timer pattern: `docs/lessons.md:35` (B247 — sub-second tick + dedup). AudioContext handling: `docs/audit/D164/01_frontend_code.md:165` ("Properly handled via audio-unlock.ts with user gesture unlock, silent buffer trick, visibilitychange re-resume"). Wall-clock for iOS Safari suspension: `docs/audit/D216/findings.md:25, 90, 115, 195` (extensively traced). UUID loss on iOS Safari PWA: **not found in any mounted file** — only inferred from the existence of recovery codes. CLAUDE.md has zero hits on any of the three. | Consolidate the three concerns into a new short subsection in `CLAUDE.md` §"Frontend" (proposed: "iOS PWA constraints"), each bullet citing its existing source (`lessons.md:35`, `D164/01_frontend_code.md`, `D216/findings.md`). UUID loss is a true gap inside this PARTIAL — write a fresh line for it. **Eligible for C237 follow-up.** |
| Recovery codes (`CLIMB-XXXX`) rationale: interim solution for UUID loss on iOS Safari PWA | `CLAUDE.md` | **TRUE_GAP** | `CLAUDE.md:191-192` lists endpoints `/api/user/recovery-code` and `/api/user/recover` with one-line "Get or create recovery code" / "Recover account from recovery code" — purely mechanical, no rationale. `PROJECT_BRIEF.md:32` mentions `recovery_codes` only as a Supabase table name. `docs/lessons.md` does not exist for this topic. The "why this exists" is undocumented. | Add one-line rationale next to the endpoint rows, or fold into the "iOS PWA constraints" subsection in the row above. **Eligible for C237 follow-up.** |
| Brief priority taxonomy P1/P2/P3/P4 | `docs/ROADMAP_CURRENT.md` (top) | **TRUE_GAP** | Used 30+ times across `ROADMAP_CURRENT.md` (lines 21, 23, 47, 51, 55, 57, 76, 109, 110, 116, 118, 227, …) but **never defined**. Zero hits in CLAUDE.md. Header lines like "P2 highlights", "Post-launch (P2)", "Open P3" assume reader knows the taxonomy. | One-paragraph definition at the top of `docs/ROADMAP_CURRENT.md` (suggested: P1 = ship-blocking, P2 = post-launch, P3 = polish, P4 = backlog/future). **Eligible for C237 follow-up.** |
| "Run `python scripts/next_brief.py` before assigning a brief number" | `CLAUDE.md` | **ALREADY_PRESENT** | `CLAUDE.md` §"Workflow rules" (~line 225): "Before assigning a new brief number, ALWAYS run `python scripts/next_brief.py` …" | No action. |
| Bibliography (Hörst, Lattice, Eva López, Tyler Nelson, Hooper's Beta) | `docs/literature_review_climbing_training.md` + KB project | **ALREADY_PRESENT** | `CLAUDE.md` §"Documentation architecture" lists `docs/literature_review_climbing_training.md` and `docs/docs_literature_hangboard.md`. KB project is a separate claude.ai project per `ROADMAP_CURRENT.md` §"Priority 2.75". | No action. |

**Verification summary:**
- 3 confirmed TRUE_GAP (planner-iterates-gyms, recovery-code rationale, P1/P2/P3/P4 taxonomy)
- 1 PARTIAL (iOS PWA quirks — three sources to consolidate, plus UUID-loss line is a fresh write)
- 1 DUBIOUS_CLAIM (gym lookup by name — must validate against code before patching docs)
- 2 ALREADY_PRESENT (drop)

**Net follow-up scope (C237 candidate):** ~3 short additions to `CLAUDE.md` (planner-gym bullet + iOS PWA constraints subsection consolidating 3 sources + recovery-code rationale) + 1 paragraph at the top of `ROADMAP_CURRENT.md` (priority taxonomy). Estimated XS, single commit, no STOP gate. Excludes the gym-lookup-by-name claim, which needs code verification first.

---

## 4. Acceptance check

| Criterion | Result |
|---|---|
| New description ≤ 60 lines | ✅ 52 lines |
| Zero numeric counters | ✅ |
| Zero deployment URLs | ✅ |
| Zero "planned" / "WIP" / "live" markers | ✅ |
| Source-of-truth rule explicit and unambiguous | ✅ §"Source of truth" |
| Every removed dynamic item present in a mounted file OR listed in gap table | ✅ §3 lists 5 net gaps |
| Output file at `docs/audit/D235_project_description_rewrite.md` | ✅ |

---

## 5. Follow-ups (out of scope here)

1. **Daniele**: copy §2 verbatim into claude.ai → Settings → Project → Description, replacing the current text.
2. **C237 (or next available, C-type, XS)**: patch the verified gaps from §3 into the mounted files. Scope, post-verification:
   - `CLAUDE.md` §"Engine architecture" → "Key modules" → `planner_v2.py`: one-bullet on planner gym iteration (TRUE_GAP).
   - `CLAUDE.md` §"Frontend": new subsection "iOS PWA constraints" consolidating wall-clock timer pattern (cite `lessons.md:35`), AudioContext gesture-unlock (cite `audit/D164/01_frontend_code.md:165`), and a fresh line on localStorage UUID loss → which leads into recovery codes rationale.
   - `CLAUDE.md` API endpoint table: one-line rationale next to `/api/user/recovery-code` (or remove if covered by the iOS PWA subsection above).
   - `docs/ROADMAP_CURRENT.md` top: one-paragraph P1/P2/P3/P4 priority taxonomy.
   - **Excluded** from C237: the "gym lookup by name (no gym_id)" claim — needs code verification first (see §3 DUBIOUS_CLAIM row). If validated against `user_state` schema and planner gym-resolution code, file as a separate B-brief (code/doc mismatch, not pure docs).
3. **Standing rule going forward**: when adding to the project description, ask "could this drift in 30 days?" — if yes, put it in a mounted file instead.
