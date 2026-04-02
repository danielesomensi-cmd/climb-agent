---
description: Run the Strategic Advisory Council — 5 parallel advisors + anonymized peer review + synthesis
---

# Strategic Advisory Council

You are orchestrating a strategic advisory council for climb-agent.

## Modes

- **Full mode (default)**: 11 subagent calls — 5 advisors + 5 reviewers + chairman synthesis. Deeper, slower.
- **Fast mode**: 6 subagent calls — 5 advisors + chairman synthesis. No peer review.

To activate fast mode, the user's question must begin with `--fast`. Strip that prefix before passing the question to advisors.

---

## Stage 1 — Independent Opinions

**Spawn 5 advisor subagents IN PARALLEL.** Pass each one the same prompt below. They must not see each other's responses.

Prompt to pass each advisor:
```
Analyze this strategic decision for a bootstrapped SaaS product:

[paste the user's question here]

Give your honest, unfiltered opinion. Be direct and specific. Under 200 words.
```

Subagent types to spawn: `contrarian`, `saas-expert`, `first-principles`, `niche-founder`, `executor`

Collect all 5 responses. Label them internally by advisor name (you will anonymize later).

---

## Stage 2 — Anonymized Peer Review (skip if --fast)

### 2a. Shuffle and anonymize

Take the 5 advisor responses and assign letters A–E to them in a **randomly shuffled order** (not in the order you spawned them). For example: A = Executor, B = Contrarian, C = SaaS Expert, D = First Principles, E = Niche Founder — but shuffle differently each time.

Record the mapping privately. Do NOT reveal it yet.

Build this anonymized block:
```
=== Response A ===
[full text]

=== Response B ===
[full text]

=== Response C ===
[full text]

=== Response D ===
[full text]

=== Response E ===
[full text]
```

### 2b. Spawn 5 reviewer subagents IN PARALLEL

Each reviewer is a `general-purpose` agent. Pass each one the same message (identical for all 5):

```
You are a critical reviewer in a strategic advisory council. Five advisors have independently analyzed a strategic question. Their responses have been anonymized (labeled A–E). You do not know who wrote which response.

STRATEGIC QUESTION:
[paste the original question here]

ANONYMIZED RESPONSES:
[paste the full anonymized block here]

---

Read all 5 responses carefully. Then answer these 3 questions. Be concise and direct.

1. STRONGEST: Which response (A–E) is the strongest and why? (2–3 sentences)
2. BLIND SPOT: Which response (A–E) has the biggest blind spot, and what is it? (2–3 sentences)
3. COLLECTIVE GAP: What did ALL FIVE responses miss? What question or angle was not addressed by anyone? (2–3 sentences)

Keep your total review under 150 words. Reference responses by letter only (A, B, C, D, E) — never guess who wrote them.
```

Collect all 5 peer reviews. Label them Reviewer 1 through Reviewer 5.

---

## Stage 3 — Chairman's Synthesis

Write your own synthesis as Chairman. You have:
- The original question
- All 5 advisor opinions (you know the anonymization key)
- All 5 peer reviews (full mode only)

Structure your synthesis EXACTLY like this:

```
## CONSENSUS
Where do most advisors agree? High-confidence signals. (2–3 sentences)

## KEY DISAGREEMENT
Where do they fundamentally disagree, and who has the stronger argument? (2–3 sentences)

## BLIND SPOTS FROM PEER REVIEW
[Full mode only] What did peer reviewers flag as missed by the group? (2–3 sentences)
[Fast mode: omit this section entirely]

## THE VERDICT
One clear recommendation. No hedging. (2–3 sentences)

## MONDAY MORNING ACTION
The single first domino to push — specific and actionable. Not a plan. (1–2 sentences)
```

Be decisive. Respect the solo founder constraint. Under 350 words total.

---

## Output Format

Present results in this order:

1. **Stage 1** — Show all 5 advisor responses with named headers:
   - 🔴 The Contrarian
   - 💰 SaaS Monetization Expert
   - 🔵 First Principles Thinker
   - 🟢 Niche SaaS Founder
   - ⚫ The Executor

2. **Stage 2** *(full mode only)* — Show all 5 peer reviews with headers: Reviewer 1 through Reviewer 5

3. **Stage 3** — Show the Chairman's synthesis

4. **Reveal the anonymization key** *(full mode only)*:
   ```
   🔓 Anonymization key: A = [Advisor Name], B = [Advisor Name], C = [Advisor Name], D = [Advisor Name], E = [Advisor Name]
   ```

---

## Save Report

Save the full report to `docs/council_reports/council_YYYY-MM-DD_HH-MM.md` (create the directory if it doesn't exist).

Report contents:
- The original question
- Mode used (full / fast)
- All 5 advisor analyses (with names)
- All 5 peer reviews (full mode only)
- Chairman's synthesis
- Anonymization key (full mode only)

Print when done: `Council complete — report saved to docs/council_reports/council_YYYY-MM-DD_HH-MM.md`
