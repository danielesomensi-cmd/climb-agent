/**
 * B396 review — structural guards on /today (the page is too large to render
 * here; the behaviour behind each guard is pinned elsewhere: the chunk
 * boundary in b396-review-chunk-offline, invalidateOutdoor in
 * b398-outdoor-invalidation).
 *
 * 1. The end-of-cycle dialog (next/dynamic) was mounted as soon as the banner
 *    could show: offline, its never-cached chunk threw on mount and sent
 *    /today into the error boundary without a tap. It is mounted on the first
 *    tap, behind a ChunkErrorBoundary, and preloaded while idle and online.
 * 2. After logging or editing an outdoor day, /today refreshed the weeks (log)
 *    or state + week + resolves (edit) but never ['outdoor','sessions'], where
 *    the card's routes come from: the card showed the old routes. /week was
 *    fixed in B398 (O1); /today now goes through the same invalidation.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { stripComments } from "./helpers/source-scan";

const code = stripComments(
  readFileSync(join(process.cwd(), "src/app/(main)/today/page.tsx"), "utf8"),
);

function fnBody(name: string): string {
  const start = code.indexOf(`async function ${name}(`);
  expect(start, `${name} not found`).toBeGreaterThan(-1);
  return code.slice(start, code.indexOf("\n  }\n", start));
}

describe("/today — StartNewMacrocycleDialog", () => {
  it("is mounted on the first tap, not as soon as the banner can show", () => {
    expect(code).not.toMatch(/cycleStatus\.canShow\s*\|\|\s*newCycleDialogOpen/);
    const at = code.indexOf("<StartNewMacrocycleDialog");
    expect(at).toBeGreaterThan(-1);
    const before = code.slice(Math.max(0, at - 600), at);
    expect(before).toMatch(/\{newCycleMounted && \(/);
    // The banner's button is what mounts it.
    expect(code).toMatch(/setNewCycleMounted\(true\);\s*setNewCycleDialogOpen\(true\);/);
  });

  it("is wrapped in a ChunkErrorBoundary that closes it with a toast", () => {
    const at = code.indexOf("<StartNewMacrocycleDialog");
    const before = code.slice(Math.max(0, at - 600), at);
    const boundary = before.lastIndexOf("<ChunkErrorBoundary");
    expect(boundary, "no ChunkErrorBoundary around the dialog").toBeGreaterThan(-1);
    const onError = before.slice(boundary);
    expect(onError).toContain("setNewCycleDialogOpen(false)");
    expect(onError).toContain("setNewCycleMounted(false)");
    expect(onError).toContain("toast(CHUNK_OFFLINE_MESSAGE");
    expect(code).toContain(`CHUNK_OFFLINE_MESSAGE = "Needs a connection — try again when you're online"`);
  });

  it("its chunk is preloaded while idle and online when the banner is on screen", () => {
    expect(code).toMatch(
      /if \(!showNewCycleBanner \|\| !online\) return;\s*return scheduleIdle\(\(\) => \{\s*loadStartNewMacrocycleDialog\(\)\.catch/,
    );
  });
});

describe("/today — outdoor log / edit refresh the routes (as /week, B398 O1)", () => {
  it("handleOutdoorLogSuccess refreshes the outdoor keys", () => {
    const log = fnBody("handleOutdoorLogSuccess");
    // Synced by the server: outdoor + weeks in one go.
    expect(log).toContain("await invalidateOutdoor(qc)");
    // Not synced: the week is written from the events response, the outdoor
    // list still has to refetch.
    expect(log).toContain("queryKeys.outdoorAll");
  });

  it("handleEditOutdoorSuccess refreshes the outdoor keys, not just state/week", () => {
    const edit = fnBody("handleEditOutdoorSuccess");
    expect(edit).toContain("await invalidateOutdoor(qc)");
    expect(edit).not.toContain("refetchAll");
  });
});
