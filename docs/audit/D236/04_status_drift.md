# D236 — Subagent D: Stale status markers

Findings: P0=1, P1=6, P2=4, P3=2

Severity legend:
- P0 = blocking lie (e.g. doc says "Stripe disabled" while sk_live runs in prod)
- P1 = clear stale marker that contradicts production behavior
- P2 = stale marker for low-impact area
- P3 = ambiguous / generic TODO without specific drift evidence

---

## Primary findings table

| file:line | quoted_phrase (≤ 100 chars) | current_reality | severity | suggested_action |
|-----------|----------------------------|-----------------|----------|------------------|
| `PROJECT_BRIEF.md:76` | `"Stripe (code complete, sk_test verified — temporarily disabled for open beta)"` | LIVE | P0 | REPLACE_TEXT → `"Stripe LIVE (sk_live keys on Railway + Vercel, since 2026-04-16)"` |
| `docs/ROADMAP_CURRENT.md:85` | `"> Stripe status: A159 implemented in TEST MODE. Not live. Currently disabled for beta period."` | LIVE | P1 | REPLACE_TEXT → `"> Stripe status: LIVE since 2026-04-16. sk_live keys on Railway + Vercel. B226 hardening done."` |
| `docs/ROADMAP_CURRENT.md:89` | `"Week 0 (now): Beta testers using the app (4-5 users). Stripe disabled. Founder dry-run."` | LIVE | P1 | REPLACE_TEXT → `"Week 0 (archived): Beta testers using the app (4-5 users). Stripe disabled at that time. Stripe went live 2026-04-16."` |
| `docs/ROADMAP_CURRENT.md:388` | `"Decided: EUR 14.99/month, 14-day trial, Founding Climber EUR 9.99 lifetime for first 50 users"` | RESOLVED_DIFFERENTLY | P1 | REPLACE_TEXT → `"Decided: USD $9.99/month Standard (15-day trial) + USD $4.99/month Founding Climber (first 20 users). Live since 2026-04-16."` |
| `CLAUDE.md:144` | `"replanner_v1.py — 13 indoor + 3 outdoor intents"` | LIVE | P1 | REPLACE_TEXT → `"replanner_v1.py — 15 indoor + 4 outdoor intents"` (confirmed via INTENT_TO_SESSION=15 keys, OUTDOOR_INTENT_TO_DISCIPLINE=4 keys) |
| `PROJECT_BRIEF.md:45` | `"Macrocycle (Hörst 4-3-2-1 + DUP, 10-13 weeks, 5 phases)"` | RESOLVED_DIFFERENTLY | P1 | REPLACE_TEXT → `"Macrocycle (Hörst 4-3-2-1 + DUP, 8–16 weeks, 5 phases)"` (A218: boulder floor=8, lead floor=11, max=16) |
| `docs/design_system_v1.md:254` | `"Downstream briefs (planned): A215 Paywall redesign, A216 Onboarding redesign, A217 Today redesign"` | LIVE | P1 | REPLACE_TEXT → `"Downstream briefs: A215 ✅ (2026-04-27), A216 ✅ (2026-04-27), A217 ✅ (2026-04-27)"` |
| `docs/DESIGN_GOAL_MACROCICLO_v1.1.md:461` | `"## 12b. Guided Session Mode (spec futura)"` | LIVE | P2 | REPLACE_TEXT → `"## 12b. Guided Session Mode (implemented — /guided/[date]/[sessionId])"` |
| `docs/DESIGN_GOAL_MACROCICLO_v1.1.md:457` | `"Guided Session Mode \| Timer UI con rest timer colorato \| Spec completa in §12b"` | LIVE | P2 | REPLACE_TEXT → append `(✅ implementato, /guided/[date]/[sessionId]; rest timer coloring parziale)` |
| `docs/vocabulary_v1.md:766` | `"required_context: constraints on location/equipment (future hardening)"` | UNKNOWN | P2 | LEAVE_AS_IS — field exists in schema but not used in resolver filtering; "future hardening" is accurate |
| `docs/beta_feedback.md:57` | `"**Status:** TODO"` (FB-3 Sunday reminder, B42) | STILL_PLANNED | P3 | LEAVE_AS_IS — B42 appears in ROADMAP_v2 as TODO, never marked done. Status accurately reflects open backlog item. |
| `PROJECT_BRIEF.md:30` | `"4 beta testers (Christie, Cesar, Paolo, Agustin) — will need to subscribe after B202"` | UNKNOWN | P3 | LEAVE_AS_IS — may be accurate (whether they subscribed is not verifiable from docs alone), but phrasing implies future action that has already occurred. Low-impact. |

---

## High-impact findings

### P0 — `PROJECT_BRIEF.md:76`: Stripe described as sk_test / disabled

**Exact lie:** `| Payments | Stripe (code complete, sk_test verified — temporarily disabled for open beta) |`

**Suggested replacement:** `| Payments | Stripe LIVE (sk_live keys on Railway + Vercel, since 2026-04-16). Two-tier: $9.99/mo Standard (15-day trial) + $4.99/mo Founding Climber (first 20 users). B202 fail-closed guard, B226 webhook hardening. |`

**Why it matters:** PROJECT_BRIEF.md is the primary status document. Any reader (Daniele or a future contributor) seeing this row will incorrectly believe Stripe is still in test/disabled mode, which contradicts the live sk_live production keys running payments today.

---

### P1 — `docs/ROADMAP_CURRENT.md:85–89`: GTM Sprint intro block says Stripe TEST MODE / disabled

**Exact lies (two lines):**
- Line 85: `> Stripe status: A159 implemented in TEST MODE. Not live. Currently disabled for beta period.`
- Line 89: `- **Week 0 (now):** Beta testers using the app (4-5 users). Stripe disabled. Founder dry-run.`

**Suggested replacement for line 85:**
`> Stripe status: LIVE since 2026-04-16. sk_live keys configured on Railway + Vercel. B202 fail-closed guard + B226 webhook hardening deployed. Two-tier pricing: $9.99/mo Standard (15-day trial) + $4.99/mo Founding Climber.`

**Suggested replacement for line 89:**
`- **Week 0 (archived, ~2026-04-01):** Beta testers using the app (4-5 users). Stripe disabled at that time.`

**Why it matters:** This block is in the active roadmap under "Priority 1.75 — Go-to-Market Sprint", which is read before every GTM brief. The word "now" in "Week 0 (now)" makes it look like a current status. Anyone reading the roadmap without reading the rest of the document will conclude Stripe is currently disabled — the opposite of production truth.

**Note:** D229 (Open P2) is already tracking this drift along with intent counts and endpoint counts. This finding amplifies why D229 should be closed soon.

---

### P1 — `docs/ROADMAP_CURRENT.md:388`: Stale pricing decision row

**Exact lie:**
`- ~~Pricing model definition~~ ✅ Decided: EUR 14.99/month, 14-day trial, Founding Climber EUR 9.99 lifetime for first 50 users`

**Suggested replacement:**
`- ~~Pricing model definition~~ ✅ Decided (final): USD $9.99/month Standard (15-day trial) + USD $4.99/month Founding Climber (first 20 users). Currency: USD. Live since 2026-04-16.`

**Why it matters:** This row uses ✅ done marker and the word "Decided", making it look authoritative. But the currency (EUR→USD), amounts ($14.99→$9.99, $9.99→$4.99), trial duration (14→15 days), and user cap (50→20) are all wrong. Any reader using this as a pricing reference for marketing, legal, or Stripe configuration will have wrong numbers.

---

### P1 — `CLAUDE.md:144`: Intent count wrong (13+3 vs actual 15+4)

**Exact lie:**
`- \`replanner_v1.py\` — 13 indoor + 3 outdoor intents, ripple effects, equipment-aware overrides, quick-add`

**Suggested replacement:**
`- \`replanner_v1.py\` — 15 indoor + 4 outdoor intents, ripple effects, equipment-aware overrides, quick-add`

**Verification:** `INTENT_TO_SESSION` dict in `backend/engine/replanner_v1.py:84–100` has exactly 15 keys (rest, recovery, technique, strength, power, power_endurance, aerobic_endurance, core, prehab, flexibility, finger_maintenance, finger_max, projecting, endurance, hard). `OUTDOOR_INTENT_TO_DISCIPLINE` dict at line 103–108 has 4 keys (outdoor_easy, outdoor_projecting, outdoor_volume, outdoor_boulder).

**Why it matters:** CLAUDE.md is the primary reference document for Claude Code. Wrong intent counts cause incorrect analysis in briefs that touch the replanner. D229 (Open P2) already tracks this.

---

### P1 — `PROJECT_BRIEF.md:45`: Macrocycle week range "10-13" vs actual 8–16

**Exact lie:**
`→ Macrocycle (Hörst 4-3-2-1 + DUP, 10-13 weeks, 5 phases)`

**Suggested replacement:**
`→ Macrocycle (Hörst 4-3-2-1 + DUP, 8–16 weeks, 5 phases)`

**Verification:** `backend/engine/macrocycle_v1.py` defines `_MAX_TOTAL_WEEKS = 16` (line 282), `_MIN_TOTAL_WEEKS_BOULDER = 8` (line 279), `_MIN_TOTAL_WEEKS_LEAD = 11` (line 261). A218 capped total at 16. The correct range is boulder: 8–16, lead: 11–16. The combined range is "8–16 weeks" depending on discipline.

**Why it matters:** Any new brief that proposes macrocycle duration changes will use this range as a baseline. Using "10-13" as the range will produce incorrect analysis — e.g., underestimating max duration, treating 14-16 week plans as illegal.

---

### P1 — `docs/design_system_v1.md:254`: A215/A216/A217 listed as "planned"

**Exact lie:**
`- **Downstream briefs (planned):** A215 Paywall redesign, A216 Onboarding redesign, A217 Today redesign`

**Suggested replacement:**
`- **Downstream briefs (completed):** A215 Paywall redesign ✅ (2026-04-27), A216 Onboarding redesign ✅ (2026-04-27), A217 Today redesign ✅ (2026-04-27)`

**Verification:** All three confirmed ✅ Done (2026-04-27) in `docs/ROADMAP_v2.md` lines 1195–1197.

**Why it matters:** design_system_v1.md is used as context when writing briefs that touch the frontend design system. Labeling live A214 downstream work as "planned" suggests there are open migration tasks — causing spurious work requests.

---

## False-positive notes

The following phrases matched grep patterns but were excluded after inspection:

1. **`docs/ROADMAP_CURRENT.md` open priority items**: Many "planned" / "TBD" / "Open" hits appear inside the Priority 1.25/1.75/2/2.25 tables as legitimate open roadmap items (B207, A-B6, A-B8, R142, D229, GTM-05, B228 etc.). These are correctly labeled and tracked — NOT findings.

2. **`docs/ROADMAP_CURRENT.md:98` — "€14.99/mo"**: This appears in GTM-02b asking "would they pay €14.99/mo". This is a historical beta-feedback question from the pre-decision period (council Run 1 pricing scenario). It describes what *testers were asked*, not current pricing. LEAVE_AS_IS.

3. **`docs/ROADMAP_CURRENT.md:130-131` — council divergence prices**: These are Strategic Advisory Council deliberation notes ("Price: €14.99/mo (Run 1) vs €9.99/mo..."). They describe the council's two scenarios, not a pricing claim. LEAVE_AS_IS — historical record.

4. **`docs/DESIGN_GOAL_MACROCICLO_v1.1.md:455` — LLM Coach in "Decisioni tecniche (approvate)"**: The table header means "approved design decisions" (architectural choices), not "implemented features". LLM Coach is included as an approved future direction, alongside implemented things. This is misleading but within the design doc's purpose. Excluded as P3 ambiguous.

5. **`docs/vocabulary_v1.md:847-848` — `outdoor_season (future)` and `maintenance (future)` goal types**: Confirmed in `macrocycle_v1.py` that neither `outdoor_season` nor `maintenance` are supported discipline values — only `lead`, `boulder`, `all_round`. These labels are accurately marked future. LEAVE_AS_IS.

6. **`docs/ENGINE_ARCHITECTURE.md:470` — "Streak is reserved for future rules (currently unused beyond tracking)"**: Confirmed in `backend/engine/adaptation/closed_loop.py:51` (`_ = streak  # reserved for future rules`). The streak IS tracked but NOT used in multiplier computation. The doc is accurate. LEAVE_AS_IS.

7. **`docs/audit/D205_subscription_audit_2026_04_16.md`**: This closed audit documented issues at a specific point in time (2026-04-16). Phrases like "`customer.deleted` is NOT handled" describe the pre-B226 state. B226 remediated these. Historical record — NOT a finding.

8. **`docs/audit_readonly_2026-04-25.md:115`**: This audit already notes the Stripe internal contradiction in ROADMAP_CURRENT. Historical diagnostic document — not an actionable drift finding on its own.

9. **`docs/vocabulary_v1.md:789` — `prescription_schema: placeholder describing reps/time scheme (format only; not used for filtering)`**: The word "placeholder" here describes the field's semantic role in the schema (descriptive only), not a development state. The code confirms this field is not used in resolver filtering. Accurate description. LEAVE_AS_IS.

10. **`CLAUDE.md:257` — "fallback to legacy UUID system (local dev only)"**: This is accurate — when `CLERK_SECRET_KEY` is absent (`is_clerk_configured()` returns False), the backend falls back to UUID-only auth. Correctly describes dev-only behavior. LEAVE_AS_IS.

11. **`docs/user_guide_v1.md`**: All occurrences of "planned" refer to "planned session" (a session status value: planned/done/skipped) — domain vocabulary, not development status. LEAVE_AS_IS.

12. **`docs/beta_feedback.md:57` (FB-3 Status: TODO)**: B42 "Sunday reminder" appears as TODO in ROADMAP_v2 (archived) and is NOT marked done anywhere. This is legitimately still open or deferred. LEAVE_AS_IS as P3.

13. **`docs/DESIGN_GOAL_MACROCICLO_v1.1.md:448` — Supabase decision**: Row correctly says "Migrazione completata. `STORAGE_BACKEND=supabase` in produzione". Accurate — Supabase IS live. LEAVE_AS_IS.

14. **`docs/design_system_v1.md:43` — `fg-disabled`**: "disabled inputs, placeholder-style dims" — CSS token naming, not a status marker. LEAVE_AS_IS.
