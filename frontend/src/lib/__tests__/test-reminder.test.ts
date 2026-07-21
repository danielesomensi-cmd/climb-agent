import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { stripComments } from "./helpers/source-scan";

/**
 * A246 (closes F52) — the wiring that was missing for the whole life of the
 * feature.
 *
 * The backend emitted the reminder, an endpoint existed to answer it, and both
 * had unit tests — but no client code read the payload or called the endpoint,
 * so periodic recalibration never happened for anyone. These tests pin the
 * three links in the chain, because each one was individually plausible and
 * collectively useless.
 */
const src = (rel: string) =>
  stripComments(readFileSync(join(process.cwd(), "src", rel), "utf8"));

const api = src("lib/api.ts");
const today = src("app/(main)/today/page.tsx");
const card = src("components/training/test-reminder-card.tsx");
const types = src("lib/types.ts");
const python = readFileSync(
  join(process.cwd(), "..", "backend/engine/planner_v2.py"),
  "utf8",
);

describe("link 1 — the payload is typed", () => {
  it("getWeek declares test_reminder", () => {
    expect(api).toMatch(/test_reminder\?:\s*TestReminder/);
  });

  it("the option union matches the backend's list exactly", () => {
    const backendOptions = python.match(/"options":\s*\[([^\]]+)\]/)?.[1] ?? "";
    for (const option of ["confirm", "postpone_1_week", "skip_cycle"]) {
      expect(backendOptions, `backend dropped ${option}`).toContain(option);
      expect(types, `TestReminderOption is missing ${option}`).toContain(option);
    }
  });
});

describe("link 2 — something reads it", () => {
  it("/today pulls the reminder off the week payload", () => {
    expect(today).toContain("test_reminder");
  });

  it("/today renders the card", () => {
    expect(today).toContain("<TestReminderCard");
  });
});

describe("link 3 — the answer reaches the engine", () => {
  it("an api client function targets the real endpoint", () => {
    expect(api).toContain("/api/week/test-reminder-response");
    expect(api).toContain("respondToTestReminder");
  });

  it("the card calls it", () => {
    expect(card).toContain("respondToTestReminder");
  });

  it("the card renders a button per option, driven by the payload", () => {
    // Not a hardcoded list: if the backend ever adds or drops an option the UI
    // follows, instead of offering a button the API would reject.
    expect(card).toMatch(/reminder\.options\.map/);
  });

  it("the card surfaces a failure instead of pretending it saved", () => {
    expect(card).toContain("toast.error");
  });

  it("has no silent dismiss — every exit path tells the engine something", () => {
    // An ✕ that just hides the card would put us back where we started: a
    // reminder that never produces a decision.
    expect(card).not.toMatch(/onDismiss|setDismissed|dismissKey/);
  });
});
