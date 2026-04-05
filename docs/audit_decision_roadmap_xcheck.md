# D-ROADMAP-XCHECK — Decision → Roadmap Cross-Check Audit

> **Date:** 2026-04-05  
> **Type:** D (read-only, no code changes)  
> **Scope:** Decision IDs D01–D91, R-01–R-06

---

## Summary

| Group | Label | Total | Found ✅ | Partial ⚠️ | Missing ❌ |
|-------|-------|-------|----------|-----------|----------|
| A | v1 Implemented | 60 | 59 | 1 | 0 |
| B | v2 Roadmap Decisions | 18 | 3 | 0 | 15 |
| C | v3 Future | 6 | 0 | 0 | 6 |
| D | Superseded | 3 | 0 | 0 | 3 |
| E | Reserved (should not appear) | 3 | — | — | 0 ✅ |

**Key finding:** Group A is fully covered. Groups B, C, D are largely absent from the roadmap — only the three deferred test-protocol decisions (D87b, D89, D91) appear. The rest exist only in the mega-brief source document, not in `ROADMAP_CURRENT.md`.

---

## Full Audit Table

### Group A — v1 Implemented

All should appear in the "Mega Brief v1" session table (lines 16–28) and/or the backlog section.

| ID | Title (short) | Found in Roadmap? | Notes |
|----|---------------|-------------------|-------|
| D01 | Assessment & Onboarding | ✅ Found | Session 1 implemented table |
| D38 | Assessment & Onboarding | ✅ Found | Session 1 implemented table |
| D68 | Assessment & Onboarding | ✅ Found | Session 1 implemented table; also line 458 |
| D80 | Assessment & Onboarding | ✅ Found | Session 1 implemented table |
| D81 | Assessment & Onboarding | ✅ Found | Session 1 implemented table |
| D83 | Assessment & Onboarding | ✅ Found | Session 1 implemented table |
| D84 | Test Protocol Revision | ✅ Found | Session 1b implemented table; lines 467, 471 |
| D84b | Test Protocol Revision | ✅ Found | Session 1b implemented table |
| D85 | Test Protocol Revision | ✅ Found | Session 1b implemented table |
| D86 | Test Protocol Revision | ✅ Found | Session 1b implemented table |
| D88 | Test Protocol Revision | ✅ Found | Session 1b implemented table |
| D90 | Test Protocol Revision | ✅ Found | Session 1b implemented table |
| D10 | Overcoming isometric pull exercise | ✅ Found | Deferred to v2; backlog ~line 865 |
| D11 | Exercise DB — Strength | ✅ Found | Session 2 implemented; line 466 |
| D12 | Exercise DB — Strength | ✅ Found | Session 2 implemented; line 466 |
| D39 | Exercise DB — Strength | ✅ Found | Session 2 implemented; line 466 |
| D50 | Three named repeater protocols | ✅ Found | Deferred to v2; backlog ~line 867 |
| D72 | grip_type field on hangboard | ✅ Found | Deferred to v2; backlog ~line 870; line 458 |
| D37 | Core activation drills from Matros | ✅ Found | Deferred to v2; backlog ~line 866 |
| D43 | Exercise DB — Conditioning | ✅ Found | Session 3 implemented table |
| D55 | Exercise safety blacklist | ✅ Found | Session 3 (implemented with note); backlog ~line 868 |
| D56 | Exercise DB — Conditioning | ✅ Found | Session 3 implemented table |
| D57 | Exercise DB — Conditioning | ✅ Found | Session 3 implemented table |
| D60 | Exercise DB — Conditioning | ✅ Found | Session 3 implemented; line 455 (KB) |
| D76 | Technique drills in free session | ✅ Found | Session 3 implemented; lines 454, 731–732 |
| D33 | Dedicated generate_warmup() | ✅ Found | Deferred to v2; lines 455, 460, 469, 829 |
| D36 | PAP (Post-Activation Potentiation) | ✅ Found | Deferred to v2; backlog ~line 830 |
| D74 | silent_feet auto-inject in warmup | ✅ Found | Deferred to v2; backlog ~line 831 |
| D34 | EL (Effort Level) as primary metric | ✅ Found | Session deferred; backlog ~line 809 |
| D52 | EL prescription table | ✅ Found | Deferred; backlog ~line 810 |
| D14 | López load monitoring (EL trend) | ✅ Found | Deferred; backlog ~line 811 |
| D35 | Hangboard Logic | ✅ Found | Session 6 implemented table |
| D49 | Don't combine MaxHangs + IntHangs | ✅ Found | Deferred; backlog ~line 847 |
| D47 | Varied-intensity intervals | ✅ Found | Deferred; backlog ~line 846 |
| D48 | Endurance & Intervals | ✅ Found | Session 7 implemented (A141) |
| D53 | Active recovery progression | ✅ Found | Deferred; backlog ~line 832 |
| D51 | Climbing vs conditioning ratio | ✅ Found | Deferred; backlog ~line 838 |
| D54 | Conditioning & Ratio | ✅ Found | Session 8 implemented |
| D58 | YTW raises exercise | ✅ Found | Session 8 (partial); backlog ~line 869 |
| D59 | Hypertonic/inhibited muscle ref | ✅ Found | Deferred; backlog ~line 839 |
| D73 | Technique drill % allocation | ✅ Found | Deferred; lines 454, 732, 840 |
| D78 | Session 8 implemented (A141) | ✅ Found | Session 8 |
| D15 | Coaching cue / onboarding UX | ⚠️ Partial | Mentioned in Session 10 context, no explicit ID section |
| D19 | Simplified linear periodization | ✅ Found | Deferred; backlog ~line 817 |
| D20 | Overreach + taper before Perf phase | ✅ Found | Deferred; backlog ~line 818 |
| D21 | Periodization & Load | ✅ Found | Session 9 implemented |
| D44 | ARC ≥6 weeks in Base phase | ✅ Found | Partial note; backlog ~line 819 |
| D45 | ARC <25% MVC enforcement | ✅ Found | Deferred; backlog ~line 820 |
| D69 | ACWR-based load monitoring | ✅ Found | Deferred; lines 674, 821 |
| D70 | Overtraining detection heuristics | ✅ Found | Deferred; lines 457, 822 |
| D71 | <10% weekly volume increase cap | ✅ Found | Deferred; backlog ~line 823 |
| D17 | Coaching & UX | ✅ Found | Session 10 implemented; line 457 |
| D29 | Post-climb mental reflection | ✅ Found | Deferred; lines 453, 853 |
| D30 | Coaching & UX | ✅ Found | Session 10 implemented; line 453 |
| D41 | Campus board auto-stop rules | ✅ Found | Deferred; backlog ~line 854 |
| D64 | Coaching & UX | ✅ Found | Session 10 implemented |
| D65 | Sleep education tips | ✅ Found | Deferred; lines 456, 857 |
| D66 | Nutrition messaging | ✅ Found | Deferred; lines 456, 858 |
| D67 | Collagen + vitamin C mention | ✅ Found | Deferred; lines 456, 859 |
| D75 | Route preview coaching (A141) | ✅ Found | Partial; note line 33 |
| D77 | SDT principles in copy | ✅ Found | Deferred; lines 586, 855 |
| D79 | "Train better, not more" personality | ✅ Found | Deferred; lines 586, 856 |

---

### Group B — v2 Roadmap Decisions

| ID | Title (short) | Found in Roadmap? | Notes |
|----|---------------|-------------------|-------|
| D03/R-01 | Flexibility axis | ❌ Missing | Not referenced anywhere |
| D08/R-02 | Test bank concept | ❌ Missing | Not referenced anywhere |
| D13 | Open hand test | ❌ Missing | Not referenced anywhere |
| R-03 | Technique assessment improvement | ❌ Missing | Not referenced anywhere |
| D22 | Competition taper protocol | ❌ Missing | Not referenced anywhere |
| D23 | Seasonal multi-macrocycle planning | ❌ Missing | Not referenced anywhere |
| D24 | ATR as alternative macrocycle model | ❌ Missing | Not referenced anywhere |
| D25 | Microcycle type granularity (6 types) | ❌ Missing | Not referenced anywhere |
| D27 | Reverse periodization for beginners | ❌ Missing | Not referenced anywhere |
| D40 | VBT for pull-up intensity tracking | ❌ Missing | Not referenced anywhere |
| D46 | BFR protocol (optional, rehab) | ❌ Missing | Not referenced anywhere |
| D61 | VO2 max benchmark + optional HIIT | ❌ Missing | Not referenced anywhere |
| D62 | Separate mobility into ROM vs postural | ❌ Missing | Not referenced anywhere |
| D63 | PNF stretching protocols | ❌ Missing | Not referenced anywhere |
| D82 | Optional menstrual cycle tracking | ❌ Missing | Not referenced anywhere |
| D87b | PE diagnostic test (repeaters 60%) | ✅ Found | Session 1b deferred; backlog ~line 876 |
| D89 | Critical Force test (simplified, 2-pt) | ✅ Found | Session 1b deferred; lines 42, 877 |
| D91 | test_pe_repeaters_60 + baselines | ✅ Found | Session 1b deferred; backlog ~line 878 |

---

### Group C — v3 Future

| ID | Title (short) | Found in Roadmap? | Notes |
|----|---------------|-------------------|-------|
| D04/R-04 | Mental/tactical assessment (LLM Coach) | ❌ Missing | Not referenced anywhere |
| D05/R-05 | Contact strength / RFD axis | ❌ Missing | Not referenced anywhere |
| D06/R-06 | Critical Force test | ❌ Missing | Not referenced anywhere |
| D31 | Route preview coaching (LLM Coach) | ❌ Missing | Not referenced anywhere |
| D32 | Fear assessment protocol (LLM Coach) | ❌ Missing | Not referenced anywhere |
| D42 | Levernier & Laffaye one-arm hang (RFD) | ❌ Missing | Not referenced anywhere |

---

### Group D — Superseded

| ID | Superseded by | Found in Roadmap? | Notes |
|----|--------------|-------------------|-------|
| D16 | → D47 | ❌ Missing | No entry; no "superseded" note |
| D18 | → D33 | ❌ Missing | No entry; no "superseded" note |
| D28 | → D75 | ❌ Missing | No entry; no "superseded" note |

---

### Group E — Reserved (should NOT appear)

| ID | Found in Roadmap? | Notes |
|----|-------------------|-------|
| D02 | ✅ Correctly absent | Not present — correct |
| D07 | ✅ Correctly absent | Not present — correct |
| D09 | ✅ Correctly absent | Not present — correct |

---

## Action Items (to decide with Daniele)

### Immediate candidates to add to ROADMAP_CURRENT.md

**Group B — v2 Roadmap (15 missing):**

These are active backlog decisions that should appear in the v2/future sections of the roadmap.

| Priority | ID | Title | Suggested section |
|----------|----|-------|-------------------|
| High | D82 | Optional menstrual cycle tracking | P4 Future / Inclusivity |
| High | D22 | Competition taper protocol | P4 Future / Periodization |
| High | D23 | Seasonal multi-macrocycle planning | P4 Future / Periodization |
| Medium | D03/R-01 | Flexibility axis in assessment | P4 Future / Assessment |
| Medium | D08/R-02 | Test bank concept | P4 Future / Assessment |
| Medium | D13 | Open hand test | P4 Future / Assessment |
| Medium | R-03 | Technique assessment improvement | P4 Future / Assessment |
| Medium | D24 | ATR as alternative macrocycle | P4 Future / Periodization |
| Medium | D25 | Microcycle type granularity | P4 Future / Periodization |
| Medium | D27 | Reverse periodization (beginners) | P4 Future / Periodization |
| Medium | D40 | VBT for pull-up intensity | P4 Future / Advanced |
| Medium | D46 | BFR protocol | P4 Future / Advanced |
| Low | D61 | VO2 max benchmark + HIIT | P4 Future / Conditioning |
| Low | D62 | ROM vs postural mobility separation | P4 Future / Conditioning |
| Low | D63 | PNF stretching protocols | P4 Future / Conditioning |

**Group C — v3 Future (6 missing):**

These are long-horizon items (LLM Coach era). Should appear in a v3/future section.

| ID | Title |
|----|-------|
| D04/R-04 | Mental/tactical assessment (LLM Coach) |
| D05/R-05 | Contact strength / RFD axis |
| D06/R-06 | Critical Force test |
| D31 | Route preview coaching (LLM Coach) |
| D32 | Fear assessment protocol (LLM Coach) |
| D42 | Levernier & Laffaye one-arm hang (RFD) |

**Group D — Superseded (3 missing):**

These should be documented to avoid future confusion (either in a "Superseded" appendix or inline notes).

| ID | Superseded by | Reason |
|----|--------------|--------|
| D16 | D47 | Replace 4×4, don't tweak |
| D18 | D33 | Absorbed into full warm-up |
| D28 | D75 | Upgraded to structured route preview |

---

## Next Steps

1. **Review this table** and decide which missing decisions to add
2. **Prepare a batch-add brief** to update `ROADMAP_CURRENT.md` in one commit
3. **D15** is the only Group A partial — verify if it needs an explicit ID entry or if it's intentionally merged

---

*Audit generated: 2026-04-05 — read-only, no files modified*
