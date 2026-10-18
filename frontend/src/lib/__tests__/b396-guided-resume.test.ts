import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  GUIDED_PROGRESS_EVENT,
  discardSavedSession,
  isResumableOnCard,
  readSavedProgress,
  resumeLabel,
} from "@/lib/guided-resume";
import type { DayPlan } from "@/lib/types";

/**
 * B396 — resuming from /today.
 *
 * The card's button said "Start session" while it actually resumed (B181), a
 * banner above the day repeated it, and its "Discard" deleted the saved
 * progress on one tap. Now: "Resume · 3/8" on the button, the banner only for
 * a session no card can resume, Discard undoable.
 */

class MemoryStorage {
  map = new Map<string, string>();
  getItem(k: string) { return this.map.get(k) ?? null; }
  setItem(k: string, v: string) { this.map.set(k, v); }
  removeItem(k: string) { this.map.delete(k); }
}

const KEY = "guided_session_user_1_2026-10-19_strength_long";

function saved(statuses: string[], currentIndex = 0): string {
  return JSON.stringify({
    version: 1,
    date: "2026-10-19",
    sessionId: "strength_long",
    sessionName: "Strength",
    startedAt: new Date().toISOString(),
    currentIndex,
    exercises: statuses.map((status, i) => ({ exerciseId: `ex_${i}`, status })),
  });
}

let storage: MemoryStorage;
let events: string[];

beforeEach(() => {
  storage = new MemoryStorage();
  events = [];
  vi.stubGlobal("window", {
    dispatchEvent: (e: Event) => {
      events.push(e.type);
      return true;
    },
  });
});

afterEach(() => vi.unstubAllGlobals());

describe("readSavedProgress — same rule as hasSavedProgress (what Start resumes)", () => {
  it("counts done and skipped exercises", () => {
    storage.setItem(KEY, saved(["done", "skipped", "done", "pending", "pending", "pending", "pending", "pending"], 3));
    expect(readSavedProgress(storage, KEY)).toEqual({ completed: 3, total: 8 });
  });

  it("a fresh, never-started session is not progress (the button stays 'Start session')", () => {
    storage.setItem(KEY, saved(["pending", "pending"], 0));
    expect(readSavedProgress(storage, KEY)).toBeNull();
  });

  it("moving past the first step counts even with nothing marked", () => {
    storage.setItem(KEY, saved(["pending", "pending"], 1));
    expect(readSavedProgress(storage, KEY)).toEqual({ completed: 0, total: 2 });
  });

  it("nothing saved or malformed → null", () => {
    expect(readSavedProgress(storage, KEY)).toBeNull();
    storage.setItem(KEY, "{not json");
    expect(readSavedProgress(storage, KEY)).toBeNull();
  });
});

describe("resumeLabel", () => {
  it("says where the session stands", () => {
    expect(resumeLabel({ completed: 3, total: 8 })).toBe("Resume · 3/8");
  });

  it("falls back to plain Resume without a total", () => {
    expect(resumeLabel({ completed: 0, total: 0 })).toBe("Resume");
  });
});

describe("discardSavedSession — Discard with Undo", () => {
  it("removes the progress and Undo puts back exactly what was there", () => {
    const value = saved(["done", "pending"], 1);
    storage.setItem(KEY, value);

    const restore = discardSavedSession(storage, KEY);
    expect(storage.getItem(KEY)).toBeNull();
    expect(restore).toBeTypeOf("function");

    restore!();
    expect(storage.getItem(KEY)).toBe(value);
  });

  it("announces both changes so the page and the card re-read", () => {
    storage.setItem(KEY, saved(["done", "pending"], 1));
    const restore = discardSavedSession(storage, KEY);
    restore!();
    expect(events).toEqual([GUIDED_PROGRESS_EVENT, GUIDED_PROGRESS_EVENT]);
  });

  it("Undo never overwrites a session started again in the meantime", () => {
    storage.setItem(KEY, saved(["done", "pending"], 1));
    const restore = discardSavedSession(storage, KEY);
    const fresh = saved(["pending", "pending"], 0);
    storage.setItem(KEY, fresh);

    restore!();
    expect(storage.getItem(KEY)).toBe(fresh);
  });

  it("nothing saved → nothing to undo", () => {
    expect(discardSavedSession(storage, KEY)).toBeNull();
    expect(events).toEqual([]);
  });
});

describe("isResumableOnCard — when the banner is redundant", () => {
  const day = (status?: "planned" | "done" | "skipped"): DayPlan =>
    ({
      date: "2026-10-19",
      weekday: "monday",
      sessions: [{ session_id: "strength_long", slot: "evening", location: "gym", status }],
    }) as unknown as DayPlan;
  const resume = { date: "2026-10-19", sessionId: "strength_long" };

  it("the card on screen shows Resume → no banner", () => {
    expect(isResumableOnCard(resume, day("planned"))).toBe(true);
    expect(isResumableOnCard(resume, day(undefined))).toBe(true);
  });

  it("a finished card has no start button → keep the banner", () => {
    expect(isResumableOnCard(resume, day("done"))).toBe(false);
    expect(isResumableOnCard(resume, day("skipped"))).toBe(false);
  });

  it("another day's session, or no card on screen → keep the banner", () => {
    expect(isResumableOnCard({ ...resume, date: "2026-10-18" }, day("planned"))).toBe(false);
    expect(isResumableOnCard({ ...resume, sessionId: "other" }, day("planned"))).toBe(false);
    expect(isResumableOnCard(resume, null)).toBe(false);
  });

  it("no session in progress → nothing to show", () => {
    expect(isResumableOnCard(null, day("planned"))).toBe(false);
  });
});
