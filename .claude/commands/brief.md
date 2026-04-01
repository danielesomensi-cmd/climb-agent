Read these files (in this order):
1. `CLAUDE.md` — project context, conventions, principles
2. `docs/ROADMAP_CURRENT.md` — all open items and priorities
3. `PROJECT_BRIEF.md` — current counters and architecture

Then respond with:
- **Project status** in max 3 lines (current phase, test count, recent changes)
- **Open items** — table grouped by priority:
  1. **P1 Stability** — production bugs, blockers
  2. **P2 Auth + Payments** — go-to-market blockers
  3. **P3 UI Polish** — first impression for paying users
  4. **P4 Future** — post-launch features

For each item: ID, short title, effort (S/M/L), 1 line of context.

**Important:** Only report items that are genuinely open. Cross-reference:
- If a section header says "✅ All closed" or "✅ Done", skip its contents entirely
- If a remediation brief is marked ✅ Done, all findings it covers are closed — do NOT report them
- If an individual item has ✅, skip it
- When in doubt, trust the remediation brief status over individual finding bullets

Do not write code. Do not modify files. Wait for instructions.
