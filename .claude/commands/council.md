---
description: Run the Strategic Advisory Council — 5 parallel advisors + synthesis
---

# Strategic Advisory Council

You are orchestrating a strategic advisory council for climb-agent.

## Instructions

1. **Read the question**: The user's input after `/council` is the strategic question to analyze. If no input is provided, ask for the strategic question.

2. **Spawn 5 advisor subagents IN PARALLEL**: Use the contrarian, saas-expert, first-principles, niche-founder, and executor agents simultaneously. Pass each one this prompt:

   ```
   Analyze this strategic decision for a bootstrapped SaaS product:

   [paste the user's question here]
   ```

3. **Collect all 5 responses** and present them with headers:
   - 🔴 The Contrarian
   - 💰 SaaS Monetization Expert
   - 🔵 First Principles Thinker
   - 🟢 Niche SaaS Founder
   - ⚫ The Executor

4. **Anonymize for synthesis**: Randomly assign letters A-E to the 5 responses. Record the mapping but do NOT reveal it yet.

5. **Chairman's Synthesis**: Write your own synthesis of all 5 analyses. Structure it EXACTLY like this:

   ```
   ## WHERE ADVISORS CONVERGE
   [What multiple analyses agree on — high-confidence signals. Reference by letter.]

   ## STRONGEST SINGLE INSIGHT
   [The one insight that changes the conversation. Reference by letter.]

   ## BIGGEST BLIND SPOT
   [What the group collectively missed]

   ## THE DECISION
   [One clear recommendation. No hedging.]

   ## MONDAY MORNING ACTION
   [The single first domino to push — specific and actionable]
   ```

   Be decisive. Respect the solo founder constraint. Under 300 words.

6. **Reveal the anonymization key**: Show which letter mapped to which advisor.

7. **Save the full report** to `docs/council_reports/council_YYYY-MM-DD_HH-MM.md` (create the directory if it doesn't exist). The report should contain:
   - The original question
   - All 5 advisor analyses (with names)
   - The chairman's synthesis
   - The anonymization key

Print a summary when done: "Council complete — report saved to docs/council_reports/council_YYYY-MM-DD_HH-MM.md"
