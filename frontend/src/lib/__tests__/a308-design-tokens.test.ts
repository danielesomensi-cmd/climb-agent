import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import path from "path";

/**
 * A308 — /today and /week draw their colours from the A214 tokens (globals.css:
 * warning, info, success, danger, fg-*, surface-*, phase-*, activity-free), not
 * from raw Tailwind palette shades. A raw `amber-400` next to a `warning` alert
 * gave two different "warning" colours one block apart, and a future palette
 * tweak would miss it.
 *
 * Scoped to the files A308 moved onto tokens, listed explicitly so unrelated
 * files are not held to it yet. A file added here must stay clean.
 */
const root = path.resolve(__dirname, "../../");
const read = (rel: string) => readFileSync(path.join(root, rel), "utf8");

const FILES = [
  "app/(main)/today/page.tsx",
  "app/(main)/week/page.tsx",
  "components/training/banner.tsx",
  "components/training/coach-card.tsx",
  "components/training/daily-cue-banner.tsx",
  "components/training/daily-tip-card.tsx",
  "components/training/day-card.tsx",
  "components/training/feedback-dialog.tsx",
  "components/training/key-sessions-card.tsx",
  "components/training/replan-dialog.tsx",
  "components/training/retest-status-card.tsx",
  "components/training/session-card.tsx",
  "components/training/skipped-tests-card.tsx",
  "components/training/week-alerts-card.tsx",
  "components/training/week-grid.tsx",
  "components/training/week-progress-bar.tsx",
];

const RAW_PALETTE = /(amber|zinc|slate|sky|yellow|green|purple|red)-[0-9]+/g;

describe("A308 — no raw palette colours on /today and /week", () => {
  it.each(FILES)("%s uses design tokens only", (rel) => {
    expect(read(rel).match(RAW_PALETTE) ?? [], `raw palette classes in ${rel}`).toEqual([]);
  });
});
