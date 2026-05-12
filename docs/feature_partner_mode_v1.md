# Feature Spec — Partner Training Mode v1

> **Status:** Draft
> **Author:** Daniele Somensi
> **Created:** 2026-05-07
> **Roadmap ID:** A219
> **Target file path (when committed):** `docs/feature_partner_mode_v1.md`

---

## 1. Problem statement

Lead and top-rope climbing **require a belayer**. When two climbers train together (the dominant scenario in commercial gyms and outdoor crags), only one can be on the wall at a time. A solo-designed structured session does not account for this:

- Rest intervals (typically 6–10 min for route endurance) don't naturally fit the partner's climbing tempo
- The belayer ends up "wasting" the session unless they improvise
- Users perceive the structured plan as less useful for partner training, eroding the value proposition vs. just-going-and-climbing

This is a **structural feature of the sport**, not a personal preference. Every climber doing rope work with a partner experiences it. Today no commercial climbing app addresses it explicitly.

The smallest possible intervention: let the user flag a session as "with partner" and have the engine restructure the rest pattern so the belayer's climbing time fills it naturally.

---

## 2. Scope

### In scope (v1)

- **Single-user app**: the partner does NOT need an account
- **Per-session toggle**: "Mi alleno in 2" on lead/top-rope sessions only
- **Mirror-partner assumption**: engine assumes the partner does the same exercises at a similar level (no two-profile algorithm)
- **Output transformation**: post-resolve transformer that restructures climbing blocks into alternating or blocked patterns
- **Logging**: `partner_mode: bool` flag on `session_log` for analytics
- **Frontend**: toggle on session card + alternating prompts in guided runner

### Out of scope (v1)

- Multi-user accounts, real-time sync between two app users (Phase 4+)
- Mismatched profiles (different goals, different grades, different macrocycle phases)
- Boulder, hangboard, campus, weights, mobility — natural alternation already exists, no value added
- Continuous-ARC sessions on long routes — incompatible with alternation by design
- Outdoor session integration — deferred until D168 outdoor unification
- Partner-facing UI / shared screens — explicitly rejected for v1
- Sticky setting in profile ("I always train with a partner") — possible v1.1 based on usage data

---

## 3. Design decisions

Three decisions made up-front to keep scope tight. Alternatives considered but rejected are noted for future revisitation.

### D1 — Pattern: alternating vs blocks → automatic per session type

| Pattern | When | Rationale |
|---|---|---|
| **Alternating (1-1-1-1)** | Endurance, projecting | Realistic for partner climbing tempo; user rest naturally = partner climb time |
| **Blocks (2-2-2)** | Power endurance (4×4 on route) | Preserves training stimulus; alternating would dilute the protocol |

Encoded as `partner_mode_pattern: "alternating" | "blocks"` on session metadata.

**Alternative considered:** let the user pick alternating vs blocks at runtime. Rejected — adds cognitive load on a feature meant to be a single tap.

### D2 — Partner exposure in guided runner → discrete inline cue

Between user steps, the runner shows a single transition step:

> 🪢 **Belay your partner** (≈6–8 min)

No prescription detail for the partner; no two-column layout; no implication that the app is tracking the partner. Just a transition card that signals "the app knows you're in pair, this is the rest window".

**Alternatives considered:**
- Full shared mode (partner's own prescription visible) — rejected, doubles complexity, contradicts mirror assumption
- Invisible (just a longer auto-rest with no explanation) — rejected, misses the engagement signal users care about

### D3 — Logging → flag-only

Add `partner_mode: bool` to `session_log` entries (default `false`). No effect on closed-loop adaptation, no effect on load score, no effect on progression. Pure telemetry.

Future signal for: pricing decisions (do partner-mode users convert better?), feature prioritization (multi-user v2 demand), marketing copy (% of sessions in pair).

---

## 4. Session compatibility matrix

| Session ID | Compatible | Pattern | Notes |
|---|---|---|---|
| `route_endurance_gym` | ✅ | alternating | 4–6 routes, ideal cadence |
| `route_projecting_gym` | ✅ | alternating | Few attempts, long natural rest |
| `power_endurance_gym` | ⚠️ | blocks | Process cue should warn: "blocks preserve volume but stretch effective rest — protocol is approximate" |
| `endurance_aerobic_gym` | ❌ | — | Continuous ARC on long route, alternation breaks the stimulus |
| `boulder_circuit_gym` | ❌ | — | Boulder; alternation already happens naturally |
| `limit_boulder_gym` | ❌ | — | Boulder |
| All hangboard / strength / weights / mobility / circuits | ❌ | — | Either no belayer needed or alternation is sub-3-minute and natural |

**Implementation rule:** the toggle is rendered only when `partner_mode_compatible: true` on the session metadata. Other sessions show no toggle (no greyed-out state, just absent).

---

## 5. Technical design

### 5.1 Catalog changes

Two new fields on session JSON (in `backend/catalog/sessions/v1/`):

```json
{
  "partner_mode_compatible": true,
  "partner_mode_pattern": "alternating"
}
```

Defaults: `partner_mode_compatible: false`, `partner_mode_pattern: null`. Three sessions get this enabled in v1: `route_endurance_gym`, `route_projecting_gym`, `power_endurance_gym`.

Vocabulary entry to add to `docs/vocabulary_v1.md`:

> **partner_mode_pattern** (session-level, optional): `"alternating" | "blocks" | null`. Defines how the resolver transformer restructures climbing blocks when `partner_mode=true` is requested at session start.

### 5.2 Engine: transformer

New module `backend/engine/partner_mode_v1.py` exposing:

```python
def apply_partner_mode(
    resolved_session: dict,
    pattern: str,  # "alternating" | "blocks"
) -> dict:
    """
    Post-resolve transformer. Restructures climbing blocks so that
    rest intervals are replaced with explicit 'belay partner' steps
    sized to mirror the user's own climbing tempo.

    Idempotent and side-effect free. Preserves:
    - total climbing volume (route count)
    - per-route load and grade
    - session-level load score
    - warmup and cooldown blocks (pass-through)
    """
```

Hook point: called post `resolve_session()`, pre-render. Lives outside the determinism boundary of the engine — it's a presentation-layer transformation, not a planning decision.

### 5.3 API changes

Two options, pick one in implementation phase:

**Option A (preferred):** query param on session resolve endpoint.
`GET /api/session/today?partner_mode=true` → backend resolves normally, then applies transformer if requested.

**Option B:** dedicated endpoint `POST /api/session/apply-partner-mode` that takes a resolved session and returns the transformed version.

Option A is cleaner. Option B is only worth it if the toggle should be flippable mid-session (not in v1).

### 5.4 Session log

Schema addition:

```json
{
  "session_id": "...",
  "completed_at": "...",
  "partner_mode": false  // new field, default false
}
```

No retroactive migration. No effect on `apply_feedback` or closed-loop. No effect on `progression_v1`.

### 5.5 Frontend

**Session card** (compatible sessions only):
- Toggle labeled "Mi alleno in 2" with subtitle "Adatta i recuperi al ritmo del compagno"
- State persists only for the current session (no sticky setting in v1)

**Guided runner** (when toggle on):
- Climbing block steps render in alternating sequence:
  - Step N: "🧗 La tua via — 7a, redpoint" (full prescription)
  - Step N+1: "🪢 Assicura il compagno (≈6–8 min)" (transition card, no timer pressure, just a "Done" button)
  - Step N+2: "🧗 La tua via — 7a, redpoint"
  - …
- Visual differentiation: belay steps use a muted card style to signal "this is rest for you"

**Session log submission**: include `partner_mode: true` in the `POST /api/session/done` payload when toggle was active.

---

## 6. Implementation phases

| Phase | Effort | Deliverable |
|---|---|---|
| **P1 — Backend foundation** | 3–4 days | Catalog field additions, transformer module, log schema, unit tests |
| **P2 — Frontend integration** | 3–4 days | Toggle on session card, guided runner alternating prompts, end-to-end test |
| **P3 — Analytics & polish** | 1–2 days | Telemetry wire-up, admin dashboard counter, user_guide.md section |

**Total:** ~M (1–2 weeks of focused work). Standalone — no dependencies, no engine changes.

---

## 7. Testing strategy

**Unit (backend):**
- Transformer preserves total route count, total load, exercise sequence
- Transformer is idempotent (`f(f(x)) == f(x)`)
- Incompatible session + `partner_mode=true` → 400 or graceful pass-through (decide in P1)
- Alternating vs blocks pattern produces correct step structures

**Integration:**
- Full flow: session start with `partner_mode=true` → guided run → session done → `session_log` has `partner_mode: true`
- Closed-loop unaffected: same feedback on partner-mode session produces same load adjustment as solo session

**Manual:**
- TestFlight on iPhone, one beta tester running a real partner session in their gym
- Christie is the natural candidate (most engaged tester, climbs in pair routinely)

---

## 8. Risks and open questions

### Risks

- **PE protocol dilution**: the "blocks" pattern on `power_endurance_gym` extends effective rest beyond protocol spec. Mitigation: process cue ("partner mode preserves volume but stretches recovery — treat as approximate"). If beta feedback reports degraded PE training, drop partner_mode from PE sessions in v1.1.
- **User confusion on incompatible sessions**: silent absence of the toggle on, e.g., hangboard sessions may surprise some users. Mitigation: FAQ entry in user_guide.md ("Why can't I enable partner mode on this session?").

### Open questions (deferred)

- **Sticky setting?** If telemetry shows >50% of sessions toggled on for the same user, consider a profile-level default in v1.1.
- **Asymmetric partners (different grades)?** If 5+ users request it, design v2 with two-profile mode. Likely needs multi-user accounts (Phase 4+).
- **Outdoor integration?** Probably yes once D168 unifies outdoor and week plan, but adds nothing structurally.

---

## 9. Roadmap position

**Priority:** P3 — post-launch engagement feature. NOT a launch blocker.

**Recommended timing:** 2–4 weeks after Stripe LIVE, when first paying users are active and you have feedback signal on whether they actually train in pair. Implementing it pre-launch costs 1–2 weeks and yields zero conversion lift (none of the current beta testers have asked for it).

**Marketing angle (when shipped):** "We know how rope climbers actually train" — a concrete differentiator vs. Crimpd, Lattice, and other solo-focused apps. Strong for r/climbharder post.

---

## 10. References

- ROADMAP entry: `docs/ROADMAP_CURRENT.md` § Post-launch — A219
- Related architectural concerns: D168 (outdoor / week plan unification) — partner mode for outdoor sessions waits on this
- Origin discussion: Daniele ↔ Claude planning chat, 2026-05-07
