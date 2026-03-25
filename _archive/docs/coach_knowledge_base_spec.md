# Coach Knowledge Base — Design Spec

> **Purpose:** Translate the research knowledge base (260 refs, 83 decisions) into coach-friendly explanations that power both static rationale texts (v1) and the LLM Coach (v2).
> **Date:** 2026-03-16
> **Language:** English (user-facing)

---

## 1. THE PROBLEM

We have ~4,200 lines of research-grade knowledge. Users see a session plan and think: "Why am I doing repeaters instead of max hangs? Why is my Base phase 6 weeks? Why can't I use full crimp?"

Currently the engine outputs WHAT to do. It doesn't explain WHY.

**v1 goal:** Every element of the training plan has a readable `rationale` field.
**v2 goal:** Users can ask "why?" about anything and get a science-backed, coach-toned answer.

---

## 2. ARCHITECTURE

### v1: Static Rationale Fields

```
Exercise → exercise.rationale        "Why this exercise"
Session  → session.rationale         "Why this session today"
Phase    → phase.rationale           "Why you're in this phase"
Macro    → macrocycle.rationale      "Why your plan looks like this"
Rule     → rule.rationale            "Why this restriction exists"
```

Each rationale is a short English text (1-3 sentences), stored in the exercise/session/phase JSON. No API call needed — just render it in the UI.

### v2: LLM Coach (Claude Sonnet)

```
System prompt:
  - Coach personality guidelines (SDT, "train better not more")
  - Distilled knowledge base (the Coach KB doc)
  - Current user context (injected per-request)

User context (injected):
  - Assessment profile (5 axes, scores)
  - Current phase + week number
  - Today's session plan
  - Recent feedback trends
  - Injury history
  - Age, experience level

User asks: "Why am I doing repeaters and not max hangs?"

Claude responds using: Coach KB knowledge + user context → personalized answer
```

---

## 3. COACH KB STRUCTURE

The Coach KB is organized in 7 sections, each answering a different level of "why?"

### Section A: Exercise Rationales

For every exercise in the catalog, a rationale block:

```json
{
  "exercise_id": "repeater_lopez",
  "rationale_short": "Repeaters build finger endurance by training your tendons to sustain moderate force over time — the exact demand of route climbing.",
  "rationale_detail": "López-Rivera's research (2018) showed that intermittent hangs improve grip endurance significantly after just 4 weeks. We prescribe these in your Build phase because your endurance axis scored below your strength — you need staying power more than peak force right now.",
  "why_not_alternatives": {
    "max_hangs": "Max hangs train peak strength (neural recruitment). Your finger strength axis is already strong — repeaters address your actual limiter.",
    "density_hangs": "Density hangs target tendon tissue quality (long-term structural adaptation). Good for injury prevention but not the primary endurance builder."
  },
  "science_nugget": "Your forearm tendons take 1-3 years to fully adapt. Repeaters at 60-80% MVC create the sustained mechanical tension that drives collagen synthesis — making your tendons both stronger and more resilient."
}
```

**Fields:**
- `rationale_short` (1 sentence) — shown in session view, tooltip
- `rationale_detail` (2-4 sentences) — shown on tap/expand, can reference user profile
- `why_not_alternatives` — answers "why not X instead?" (LLM Coach uses this)
- `science_nugget` — one interesting fact (optional, for engagement)

**Template variables:** `{weakness_axis}`, `{current_phase}`, `{experience_level}`, `{user_goal}` — resolved at render time.

### Section B: Session Structure Rationales

For each session type:

```json
{
  "session_type": "hangboard_strength",
  "rationale": "Today's session focuses on finger strength because you're in the Strength & Power phase — this is when we push your neural system to recruit more muscle fibers. The warm-up prepares your tendons, the main work builds peak force, and the cooldown promotes recovery.",
  "structure_explanation": {
    "warmup": "15 minutes of progressive loading protects your tendons and primes your nervous system. Skipping warm-up is the #1 preventable injury risk.",
    "main_work": "Max hangs at high intensity (EL 2-3) for low volume. Quality over quantity — stop when speed or form drops.",
    "cooldown": "Easy traversing and stretching promote blood flow for recovery. Your muscles grow during rest, not during the workout."
  }
}
```

### Section C: Phase Rationales

For each macrocycle phase:

```json
{
  "phase": "endurance_base",
  "rationale": "You're building your aerobic foundation. Think of it like base miles for a runner — boring but essential. Your forearm capillaries need at least 6 weeks of sustained low-intensity work to grow new blood vessels. This is what lets you recover faster between moves on longer routes.",
  "what_happens_physiologically": "Capillary angiogenesis (new blood vessel growth) and mitochondrial biogenesis (more cellular power plants in your forearm muscles). These adaptations let you deliver more oxygen and clear waste products faster — the difference between pumping out on the crux and cruising through it.",
  "why_this_long": "Research shows mitochondrial adaptations require a minimum of 6 weeks of consistent aerobic stimulus (Mujika 2012). Cutting Base phase short means incomplete vascular adaptation — you'd be building strength on a weak foundation.",
  "common_mistakes": "Going too hard during ARC. If you feel ANY pump, you're above the 25% MVC threshold and switching from aerobic to anaerobic metabolism — which defeats the entire purpose."
}
```

### Section D: Periodization Rationale (Macro Level)

```json
{
  "model": "horst_4321_dup",
  "rationale": "Your training plan follows a proven 4-phase cycle: build your aerobic base, develop strength, convert it to power endurance, then peak for performance. Each phase targets different physiological adaptations in the order your body needs them.",
  "why_this_model": "Meta-analyses of 35+ studies show periodized training produces significantly better strength gains than random training (Williams 2017, Moesgaard 2022). Our model combines Hörst's climbing-specific phase sequence with undulating daily variation — you get the benefits of both structured progression and stimulus variety.",
  "why_not_other_models": {
    "no_periodization": "Training randomly works for beginners but plateaus quickly. Periodization outperforms non-periodized training by a meaningful margin (effect size 0.43).",
    "block_ATR": "ATR periodization (shorter 6-9 week cycles with multiple peaks) is excellent for competition climbers. We're considering it for v2. For now, the linear model is safer and better-validated for most climbers.",
    "reverse_periodization": "Starting with max intensity and tapering to endurance (House & Johnston 2014). Interesting theory but less evidence for climbing. Remains on our research watchlist."
  }
}
```

### Section E: Rule & Restriction Rationales

For every safety rule and gate:

```json
{
  "rule_id": "youth_age_gate_16",
  "rationale_short": "Climbers under 16 don't do max hangboard or campus board training — their growth plates are still developing.",
  "rationale_detail": "Research by Schöffl (2004-2024) documented a 600% increase in growth plate fractures in young climbers. 45% of all injuries in adolescent climbers are growth-plate related. These injuries are entirely preventable by avoiding high-intensity finger loading before skeletal maturity. This isn't about ability — it's about biology.",
  "what_instead": "Focus on climbing volume, technique drills, and general strength. Young climbers improve fastest through movement quality, not finger strength. You have decades ahead to build finger strength safely."
}
```

```json
{
  "rule_id": "open_hand_default",
  "rationale_short": "We prescribe open-hand grip for hangboard training because full crimp is the #1 cause of pulley injuries.",
  "rationale_detail": "A systematic review by Miro et al. (2021) confirmed that full crimp grip is the primary mechanism for finger pulley injuries — forces on the pulley can be 4× the fingertip force. Open-hand grip distributes load more safely. Half crimp is acceptable. Full crimp is fine on the wall where you need it, but there's no reason to use it on the hangboard where you control the variables."
}
```

### Section F: Coaching Cues Context

For process goals and coaching messages, the rationale behind each:

| Cue | Why it's there |
|-----|---------------|
| "Silent feet" warm-up | Proprioception and precision. Elite climbers use 1/5 the energy of novices — most of that gap is footwork. |
| "Preview your route" checklist | Seifert (2017): climbers who previewed more thoroughly moved more smoothly and made fewer exploratory movements. |
| "G-Tox: alternate arms during rest" | Gravity-assisted venous return. Simple technique that helps clear metabolites faster during on-wall rests. |
| "Rest day = training day" | Adaptation happens during recovery. Growth hormone surges during deep sleep. Skipping rest undermines your hard work. |
| "Fuel your training" | Low energy availability is documented across all climbing levels (Regulska-Ilow 2023). More training volume = more fuel needed. |

### Section G: FAQ Bank (for LLM Coach v2)

Pre-written Q&A pairs that the LLM Coach can draw from or adapt:

**Q: Why is my Base phase so long?**
A: Your forearm capillaries need at least 6 weeks to grow new blood vessels (angiogenesis) and build new mitochondria. Cut it short and you're building on incomplete foundations. The patience pays off — you'll recover faster between moves for the rest of the macrocycle.

**Q: Can I skip the warm-up?**
A: A meta-analysis of 32 studies (Fradkin 2010) found warm-up improves performance in 79% of measured outcomes. More importantly, warming up increases the physiological slack in your finger pulleys — the main structure that gets injured in climbing. 15 minutes of warm-up is cheap insurance.

**Q: Why can't I do both max hangs and repeaters?**
A: López-Rivera's research (2018) showed both methods improve finger strength but through different mechanisms — neural recruitment vs endurance adaptation. Combining them in one phase dilutes both stimuli and increases injury risk. Pick one per phase, alternate across macrocycles.

**Q: I'm 15, why can't I use the hangboard?**
A: Your finger growth plates haven't finished developing yet (typically by age 17). Loading them with max-weight hangs risks epiphyseal fractures — growth plate injuries that have increased 600% in young climbers over the past decade (Schöffl 2024). This isn't a limitation — it's protecting your future climbing. Focus on technique and climbing volume; that's where you'll make the biggest gains at your age.

**Q: Why open hand and not crimp on hangboard?**
A: Full crimp puts up to 4× the fingertip force on your pulleys (Miro 2021). On the wall, sometimes you need to crimp — that's fine. But on the hangboard where you control every variable, there's no reason to use the grip type most likely to injure you. Open hand is safer and builds transferable strength.

**Q: Why does my plan have so many technique drills?**
A: Because technique is the single highest-ROI training investment, especially for climbers with less than 3-5 years experience. Elite climbers use just 20% of the energy novices use on the same route (Baláš 2014). That efficiency gap comes from technique, not strength. Every minute you spend on silent feet and precise footwork pays bigger dividends than an extra set of pull-ups.

**Q: Is my plan based on real science?**
A: Every decision in your training plan traces back to peer-reviewed research, published books by credentialed experts, or established coaching methodology. The knowledge base contains 260+ references across 5 systematic reviews and 10 research topics. This isn't bro-science — it's the most comprehensive evidence-based climbing training system we could build.

**Q: Why don't you tell me to lose weight?**
A: Because it doesn't work and it's dangerous. Body composition explains less than 1% of climbing performance variance when training is controlled for (Mermier 2000). Meanwhile, disordered eating is a documented problem in climbing — 15.8% of elite female competition climbers have amenorrhoea (Joubert 2022). We focus on what actually matters: finger strength, technique, endurance, and recovery. Eat enough to fuel your training.

---

## 4. IMPLEMENTATION PLAN

### v1: Static Rationales (with mega-brief implementation)

**Step 1:** Add `rationale` field to exercise, session, phase, and macrocycle data models.

**Step 2:** Populate rationale fields:
- Exercises: write `rationale_short` for all ~167+ exercises (can be generated in batch — most follow patterns)
- Sessions: write rationale for each session type (~10 types)
- Phases: write rationale for each phase (5 phases)
- Rules: write rationale for each safety gate (~7 critical rules)

**Step 3:** UI — display rationales:
- Exercise card: small "why?" icon → tooltip or expandable text showing `rationale_short`
- Session header: "About this session" expandable section
- Phase banner: "Why this phase?" expandable
- Restriction messages: include rationale inline (e.g., "Campus board locked — [why?]")

**Estimated effort:** 1 Claude Code session for data model + UI. 1 session for batch-writing all rationale texts.

### v2: LLM Coach (Phase 3.5)

**Step 1:** Build system prompt from this Coach KB:
- Coach personality rules (from D77, D79)
- Distilled knowledge (Sections A-G condensed to fit context window)
- Response guidelines (tone, length, citation style)

**Step 2:** Build context injection pipeline:
- On each user message: inject current profile, phase, session, recent feedback
- The LLM gets: system prompt (static) + user context (dynamic) + user question

**Step 3:** API integration:
- Claude Sonnet 4 via Anthropic API
- Streaming response
- UI: chat interface within the app (separate tab or bottom sheet)

**Step 4:** Conversation scope limits:
- Coach answers questions about training, exercises, periodization, technique
- Coach does NOT: prescribe diets, diagnose injuries, give medical advice, comment on body weight
- Coach redirects out-of-scope questions: "That's outside what I can help with. I'd recommend talking to [relevant professional]."

**Estimated effort:** 2-3 Claude Code sessions (API integration + prompt engineering + UI).

---

## 5. CONTENT CREATION WORKFLOW

### How to write the ~200 rationale texts efficiently

Most exercise rationales follow patterns. Use templates:

**Strength exercise template:**
"[Exercise name] builds [target quality] by [mechanism]. We prescribe it in [phase] because [reason linked to user profile/phase]. [One science fact]."

**Drill template:**
"[Drill name] develops [skill]. [How it works in 1 sentence]. [Why it matters: efficiency/safety/technique data point]."

**Safety gate template:**
"[Restriction] exists because [evidence]. [What to do instead]. [Reassurance that this isn't limiting — it's optimizing]."

**Phase template:**
"You're in [phase name] — [goal in plain English]. [What's happening physiologically in 1-2 sentences]. [How long and why]. [Common mistake to avoid]."

**Batch generation approach:**
1. Claude can generate all rationale texts from the mega-brief + topic files
2. Daniele reviews and edits for tone/accuracy
3. Load into exercise/session/phase JSON

---

## 6. RELATIONSHIP TO EXISTING DOCS

| Doc | Role in Coach KB |
|-----|-----------------|
| Topic files (01-10) | Source of truth — rationales are simplified versions |
| `consuegra_book_synthesis.md` | Protocol details that inform exercise rationales |
| `decision_consolidation_D01_D83.md` | Maps rationale to specific decision + source |
| `claude_code_mega_brief_v1.md` | Implementation specs — Coach KB adds the "why" layer on top |
| `brief_training_methodology_explained.md` | User-facing overview (different from Coach KB: one-time read vs in-context help) |

---

## 7. EXAMPLE: FULL USER JOURNEY WITH RATIONALES

**User opens app → sees today's session:**

```
SESSION: Hangboard Strength + Conditioning
Phase: Strength & Power (Week 2 of 4)

WARM-UP (15 min)
├── Joint mobilization (3 min)
├── Easy traversing (5 min)
│   └── "Silent Feet drill — place every foot silently"
│      [why?] "Precision footwork is the single biggest energy saver
│       in climbing. Elite climbers use 1/5 the energy of novices."
├── Warm-up repeaters on 30mm (5 min)
│   [why?] "Primes your finger tendons with blood flow before heavy loading.
│    Skipping this step is the #1 preventable hangboard injury risk."

MAIN WORK
├── MaxHangs MAW 20mm: 4×5s @ +25kg, rest 3min (20 min)
│   [why?] "Your finger strength axis scored 52 — below your 7c target.
│    Max hangs at 90% MVC drive neural recruitment: your brain learns to
│    activate more muscle fibers simultaneously."
├── Eccentric pull-ups: 3×5 @ 6s descent (12 min)
│   [why?] "Builds pulling strength more effectively than band-assisted
│    pull-ups. The slow eccentric phase also strengthens tendons."

CONDITIONING
├── Nordic curls: 3×5 (8 min)
│   [why?] "The most evidence-backed injury prevention exercise.
│    51% lower injury rate in athletes who do Nordic curls (Van Dyk 2019)."
├── Face pulls: 3×15 (5 min)
│   [why?] "Counters 'climber's back' — climbing overdevelops your
│    pulling muscles. Face pulls strengthen the neglected rear delts
│    and mid-back that keep your shoulders healthy."

[About this session]
"You're in the Strength & Power phase — this is where we push your
 nervous system to recruit more muscle fibers. The focus is high
 intensity, low volume. Quality matters more than quantity today.
 Stop any set if you can't maintain good form."

[About this phase]
"Strength & Power runs for 3-4 weeks after your Base phase. Your
 capillaries are built — now we're adding the neural horsepower to
 use them. By the end of this phase, your max hang should increase
 by 5-10%. That translates directly to holding smaller holds longer."
```

---

*End of Coach Knowledge Base Design Spec*
