import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * A262 — the public assessment hands its six answers to the wizard through the
 * anonymous draft. If that write is wrong the failure is silent: the visitor
 * simply finds empty fields and retypes, or worse, finds someone's Font grade
 * sitting in a French-scale field.
 *
 * These drive the real `seedDraftFromAssessment` and the real `draftKey`, for
 * the reason spelled out in onboarding-draft-scope.test.ts: a test asserting
 * its own assumed key cannot catch a producer and a consumer drifting apart.
 */

class MemoryStorage {
  private map = new Map<string, string>();
  get length() { return this.map.size; }
  key(i: number) { return Array.from(this.map.keys())[i] ?? null; }
  getItem(k: string) { return this.map.get(k) ?? null; }
  setItem(k: string, v: string) { this.map.set(k, v); }
  removeItem(k: string) { this.map.delete(k); }
  clear() { this.map.clear(); }
}

let storage: MemoryStorage;

const LEAD_SEED = {
  discipline: "lead",
  current_grade: "7a",
  target_grade: "7c",
  max_rp: "7a",
  max_os: "6b+",
  climbing_years: 5,
  primary_weakness: "fingers_give_out",
};

const BOULDER_SEED = {
  discipline: "boulder",
  current_grade: "6C",
  target_grade: "7B",
  max_rp: "6C",
  max_os: "6A+",
  climbing_years: 4,
  primary_weakness: null,
};

beforeEach(() => {
  storage = new MemoryStorage();
  vi.stubGlobal("window", { localStorage: storage, Clerk: undefined });
  vi.stubGlobal("localStorage", storage);
  vi.resetModules();
});

afterEach(() => vi.unstubAllGlobals());

async function load() {
  return import("@/components/onboarding/onboarding-context");
}

function readAnon(draftKey: (u?: string | null) => string) {
  const raw = storage.getItem(draftKey(null));
  return raw ? JSON.parse(raw) : null;
}

describe("seedDraftFromAssessment", () => {
  it("writes under the anonymous key the wizard adopts at sign-in", async () => {
    const { seedDraftFromAssessment, draftKey } = await load();
    seedDraftFromAssessment(LEAD_SEED);
    expect(readAnon(draftKey)).not.toBeNull();
  });

  it("fills the lead grade fields for a lead answer", async () => {
    const { seedDraftFromAssessment, draftKey } = await load();
    seedDraftFromAssessment(LEAD_SEED);
    const { data } = readAnon(draftKey);
    expect(data.grades.lead_max_rp).toBe("7a");
    expect(data.grades.lead_max_os).toBe("6b+");
    expect(data.goal.current_grade).toBe("7a");
    expect(data.goal.target_grade).toBe("7c");
    expect(data.experience.climbing_years).toBe(5);
    expect(data.self_eval.primary_weakness).toBe("fingers_give_out");
  });

  it("keeps boulder answers on the boulder fields, in Fontainebleau", async () => {
    /* The engine stores boulder grades in Font and converts to the
       lead-calibrated scale server-side. Writing a converted value into
       boulder_max_rp would overwrite the climber's own number with a
       derived one. */
    const { seedDraftFromAssessment, draftKey } = await load();
    seedDraftFromAssessment(BOULDER_SEED);
    const { data } = readAnon(draftKey);
    expect(data.grades.boulder_max_rp).toBe("6C");
    expect(data.grades.lead_max_rp).toBe(""); // untouched default
    expect(data.goal.discipline).toBe("boulder");
    expect(data.goal.target_boulder_grade).toBe("7B");
  });

  it("enriches an existing draft instead of wiping it", async () => {
    const { seedDraftFromAssessment, draftKey } = await load();
    storage.setItem(
      draftKey(null),
      JSON.stringify({
        data: {
          profile: { name: "Ada", age: 30, weight_kg: 60, height_cm: 170 },
          experience: { climbing_years: 1, structured_training_years: 0 },
          grades: { lead_max_rp: "", lead_max_os: "" },
          goal: { goal_type: "lead_grade", discipline: "lead", target_grade: "", target_style: "redpoint", current_grade: "", deadline: "", total_weeks: 12 },
          self_eval: { primary_weakness: "", secondary_weakness: "pump_too_early" },
          tests: {},
        },
        deepestStep: 3,
        savedAt: Date.now(),
      }),
    );

    seedDraftFromAssessment(LEAD_SEED);
    const env = readAnon(draftKey);
    expect(env.data.profile.name).toBe("Ada"); // survives
    expect(env.data.self_eval.secondary_weakness).toBe("pump_too_early");
    expect(env.data.grades.lead_max_rp).toBe("7a"); // enriched
  });

  it("does not advance deepestStep — pre-filled is not visited", async () => {
    /* deepestStep drives the resume prompt. Claiming steps the visitor never
       saw would let the wizard skip screens they still need to answer. */
    const { seedDraftFromAssessment, draftKey } = await load();
    seedDraftFromAssessment(LEAD_SEED);
    expect(readAnon(draftKey).deepestStep).toBe(0);
  });
});
