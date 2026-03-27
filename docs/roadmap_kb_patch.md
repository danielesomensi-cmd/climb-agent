# ROADMAP PATCH — KB Research Section
> **Instructions:** Add this entire section to `ROADMAP_CURRENT.md` after "Priority 2.5b — Catalog & Polish" and before "Priority 3 — Knowledge Base v2".
> Also: apply the backlog annotation patches listed at the bottom.

---

## Priority 2.75 — KB Research Integration

> **Companion project:** The KB research lives in a **separate claude.ai project** called **"climb-agent knowledge base"**.
> All research files, Hörst syntheses, topic files, and decision consolidations live in that project's knowledge.
>
> **⚠️ RULE: Before implementing any deferred decision from the backlog below, open the KB project and check
> `horst_integration_audit.md` for enrichment material. Many deferred decisions have ready-to-use content.**

### Hörst "Training for Climbing" (3rd ed.) — Status

7 of 13 chapters synthesized into structured MD files. 0 conflicts with existing D01-D83 decisions. 14 confirmations. 6 new coaching cues proposed.

| Ch. | File | Status | Enriches Decisions |
|-----|------|--------|--------------------|
| 2 | `horst_ch2_self_assessment_synthesis.md` | ✅ | D01 (context) |
| 3 | `horst_ch3_mental_training_synthesis.md` | ✅ | D29, D30 (context) |
| 4 | `horst_ch4_technique_skill_synthesis.md` | ✅ | D73, D76 (context) |
| 6 | `horst_ch6_mobility_synthesis.md` | ✅ | **D33, D58, D60 — 38 exercises ready** |
| 11 | `horst_ch11_nutrition_synthesis.md` | ✅ | D65, D66, D67 (enrichment) |
| 12 | `horst_ch12_recovery_synthesis.md` | ✅ | **D17, D70 — quantified recovery data** |
| 13 | `horst_ch13_injury_synthesis.md` | ✅ | D68-D72 (context) |

**Key audit finding — CUE-02 (v1, affects D33):** Excessive forearm flexor static stretching before climbing reduces grip strength for up to 1 hour. The warm-up generator (D33) must not prescribe heavy forearm flexor stretches before performance sessions.

### Open KB Research Items

| Item | Status | Where |
|------|--------|-------|
| Session 2 patch (4 corrections: D11, D12, D39, D72) | ⏸️ Prepared | KB project memory (not yet a file) |
| D84 pulling strength test (max load review) | ⏸️ Under review | KB project |
| Finger strength test architecture (5s→7s Lattice) | ⏸️ Under review | KB project |
| CUE-02 formalize (forearm stretch → D33 amendment) | 📋 Proposed | `horst_integration_audit.md` §6 |
| Coach KB spec: add 8 Hörst coaching cues | 📋 Proposed | `horst_integration_audit.md` §5 |
| Decision consolidation: append D84-D91 | 📋 Proposed | `kb_gaps_analysis.md` |
| Topics 05-10 Steps 4-5 (decision specs) | ⏳ Not started | KB project |

### Remaining Books

| Book | Status | Needed for |
|------|--------|-----------|
| Bechtel — Climb Strong: Drills Manual (pp. 31-90) | 📷 Photograph physical copy | Topic 08 drills |
| MacLeod — 9 Out of 10 Climbers | 🛒 Buy (DRM-free PDF or photos) | Topics 04, 05, 07, 08 |
| Ilgner — The Rock Warrior's Way | 🛒 Buy | Topics 05, 09 |
| Mobråten — The Climbing Bible | 🛒 Buy | Topics 01, 02, 04, 07, 08 |
| Christophersen — Climbing Bible: Injuries | 🛒 Buy | Topic 07 |

---

# BACKLOG ANNOTATION PATCHES

> Apply these edits to the existing backlog entries in ROADMAP_CURRENT.md.
> Each patch adds a "See KB" note to help Claude Code find the enrichment material.

### Warm-Up & Recovery section

**D33 — change row to:**
```
| D33 | Dedicated `generate_warmup()` function | M | 5-phase protocol generator. **⚠️ KB: Ch. 6 has warm-up exercises + CUE-02 (no forearm flexor stretch pre-performance). See `horst_integration_audit.md` §5-§6.** |
```

**D53 — change row to:**
```
| D53 | Active recovery progression (3-step) | S | References EL system (D34). **KB: Ch. 12 confirms active rest +35% lactate clearance (Watts 2000).** |
```

### Exercise Catalog section

**D58 — change row to:**
```
| D58 | YTW raises exercise (missing from postural set) | XS | 4/5 done, only YTW missing. **⚠️ KB: Ch. 6 has T exercise (EX-SCAP-01) and Y exercise (EX-SCAP-02) with full protocols + 38 total exercises. See `horst_ch6_mobility_synthesis.md` §8.** |
```

### Coaching & UX section

**D65 — change row to:**
```
| D65 | Sleep education tips | S | **KB: Ch. 12 §5.5 (6-7h min, 8-10h after hard training) + Ch. 11 hydration data.** |
```

**D66 — change row to:**
```
| D66 | Nutrition messaging at phase transitions | S | **KB: Ch. 11 has macro ratios by climbing style (65:15:20 vs 55:15:30), GI tables, 3-step refueling protocol.** |
```

**D67 — change row to:**
```
| D67 | Collagen + vitamin C educational mention | XS | **KB: Ch. 11 also covers creatine (2-5g OK, loading counterproductive) + caffeine periodization.** |
```

### Periodization & Load section

**D70 — change row to:**
```
| D70 | Overtraining detection heuristics | M | 5-flag system. **⚠️ KB: Ch. 12 adds central fatigue timeline — nerve cell 7× slower recovery than muscle (Bompa 1983). If "off" after several rest days → 2-10 more days needed.** |
```

---

*End of ROADMAP patch*
