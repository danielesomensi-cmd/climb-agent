/**
 * B414 (INBOX-2026-11-04-ORPHAN) — the client side of «a session no longer in
 * the plan». On 04/11 the coach swapped the treadmill for a custom while the
 * phone played the treadmill from a cached week; the log became an orphan.
 *
 * - api.ts recognizes the refusal: 422 of /events (step 4, the engine's
 *   sentence) and 409 of /feedback (step 27, structured), never a stale plan.
 * - The choices of the box: «in place of X» = remove X + add the played
 *   session in X's slot (catalog: add_planned_session; saved custom:
 *   add_custom_session), «as an extra» only with a free slot, a generated
 *   session cannot be placed. A dry run first: «in place of X» never removes X
 *   for nothing.
 * - Start checks a cached week older than 60 s (bounded, fail-open).
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient } from "@tanstack/react-query";

import { SessionNotInPlanError, StalePlanError, applyEvents } from "@/lib/api";
import { isSessionNotInPlan, parseSessionNotInPlan } from "@/lib/session-not-in-plan";
import {
  OrphanPlacementError,
  canPlaceSession,
  orphanOptions,
  placeOrphanSession,
  placementEvents,
} from "@/lib/orphan-session";
import { sessionStillPlanned, startNeedsPlanCheck, START_CHECK_TIMEOUT_MS } from "@/lib/start-plan-check";
import { queryKeys } from "@/lib/query-keys";
import type { DayPlan, SessionSlot, WeekPlan } from "@/lib/types";

const DATE = "2026-11-04";

function slot(session_id: string, slotName: string, extra: Partial<SessionSlot> = {}): SessionSlot {
  return { session_id, slot: slotName, location: "gym", status: "planned", ...extra } as SessionSlot;
}

function day(sessions: SessionSlot[]): DayPlan {
  return { date: DATE, weekday: "wed", sessions } as unknown as DayPlan;
}

function plan(sessions: SessionSlot[], revision = 3): WeekPlan {
  return { plan_revision: revision, weeks: [{ days: [day(sessions)] }] } as unknown as WeekPlan;
}

function mockFetch(responses: Array<{ status: number; body: unknown }>) {
  const bodies: Array<Record<string, unknown>> = [];
  const fn = vi.fn(async (_url: string, init?: RequestInit) => {
    bodies.push(JSON.parse(String(init?.body ?? "{}")));
    const r = responses.shift();
    if (!r) throw new Error("unexpected fetch");
    return new Response(JSON.stringify(r.body), { status: r.status, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fn);
  return bodies;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("parseSessionNotInPlan", () => {
  it("/events 422: the engine's sentence, with day and ref", () => {
    const body = JSON.stringify({
      detail: `Session not in the plan: day=${DATE} session_ref=treadmill_hiit_4x4 slot=None (removed or replaced since the plan was loaded)`,
    });
    expect(parseSessionNotInPlan(422, body)).toEqual({ date: DATE, session_id: "treadmill_hiit_4x4", day_sessions: null });
  });

  it("/feedback 409: the structured detail", () => {
    const day_sessions = [{ session_id: "custom_cs_320de282", slot: "lunch", status: "planned", name: "VO2" }];
    const body = JSON.stringify({
      detail: { code: "session_not_in_plan", message: "x", date: DATE, session_id: "treadmill_hiit_4x4", day_sessions },
    });
    expect(parseSessionNotInPlan(409, body)).toEqual({ date: DATE, session_id: "treadmill_hiit_4x4", day_sessions });
  });

  it.each([
    ["a stale plan 409", 409, { detail: "stale", code: "stale_plan", current_revision: 4 }],
    ["another 422", 422, { detail: "Slot 'lunch' already occupied on 2026-11-04" }],
    ["a 400", 400, { detail: { code: "session_not_in_plan" } }],
  ])("not for %s", (_label, status, body) => {
    expect(parseSessionNotInPlan(status as number, JSON.stringify(body))).toBeNull();
  });

  it("not for a body that is not JSON", () => {
    expect(parseSessionNotInPlan(422, "<html>")).toBeNull();
  });
});

describe("request() throws SessionNotInPlanError", () => {
  it("on the /events 422 — not a generic ApiError, not a stale plan", async () => {
    mockFetch([
      {
        status: 422,
        body: { detail: `Session not in the plan: day=${DATE} session_ref=treadmill_hiit_4x4 slot=lunch (x)` },
      },
    ]);
    const err = await applyEvents({
      events: [{ event_type: "mark_done", date: DATE, session_ref: "treadmill_hiit_4x4" }],
      week_plan: plan([]),
    }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(SessionNotInPlanError);
    expect(err).not.toBeInstanceOf(StalePlanError);
    expect(isSessionNotInPlan(err)).toBe(true);
    expect((err as SessionNotInPlanError).status).toBe(422);
    expect((err as SessionNotInPlanError).sessionId).toBe("treadmill_hiit_4x4");
  });

  it("isSessionNotInPlan is false for other errors", () => {
    expect(isSessionNotInPlan(new Error("x"))).toBe(false);
    expect(isSessionNotInPlan(null)).toBe(false);
  });
});

describe("the choices of the box", () => {
  const custom = slot("custom_cs_320de282", "lunch", { is_custom: true, name: "VO2" } as Partial<SessionSlot>);
  const done = slot("technique_drills", "evening", { status: "done" });

  it("in place of each session still to do; extra only with a free slot", () => {
    const opts = orphanOptions(day([custom, done]), "treadmill_hiit_4x4");
    expect(opts.replace.map((s) => s.session_id)).toEqual(["custom_cs_320de282"]);
    expect(opts.extraSlot).toBe("morning");
    expect(opts.placeable).toBe(true);
    const full = orphanOptions(
      day([custom, done, slot("mobility", "morning")]),
      "treadmill_hiit_4x4",
    );
    expect(full.extraSlot).toBeNull();
  });

  it("a generated session cannot be placed back", () => {
    expect(canPlaceSession("generated_core_x")).toBe(false);
    expect(orphanOptions(day([custom]), "generated_core_x").placeable).toBe(false);
  });

  it("catalog session in place of a custom: remove + add_planned_session in that slot", () => {
    const events = placementEvents(DATE, "treadmill_hiit_4x4", {
      kind: "replace",
      target: { ...custom, location: "home" } as SessionSlot,
    });
    expect(events).toEqual([
      { event_type: "remove_session", date: DATE, session_ref: "custom_cs_320de282", slot: "lunch" },
      { event_type: "add_planned_session", session_id: "treadmill_hiit_4x4", target_date: DATE, slot: "lunch", location: "home" },
    ]);
  });

  it("saved custom as an extra: add_custom_session with its id", () => {
    expect(placementEvents(DATE, "custom_cs_abc", { kind: "extra", slot: "evening" })).toEqual([
      { event_type: "add_custom_session", custom_session_id: "cs_abc", target_date: DATE, slot: "evening" },
    ]);
  });
});

describe("placeOrphanSession — dry run first", () => {
  const custom = slot("custom_cs_320de282", "lunch");

  it("the dry run shows it on the day → the real write, then the cache", async () => {
    const placed = plan([slot("treadmill_hiit_4x4", "lunch")], 4);
    const bodies = mockFetch([
      { status: 200, body: { dry_run: true, week_plan: placed } },
      { status: 200, body: { week_plan: placed } },
    ]);
    const qc = new QueryClient();
    qc.setQueryData(queryKeys.week(0), { week_num: 9, week_plan: plan([custom]) });
    await placeOrphanSession(qc, { weekNum: 0, weekPlan: plan([custom]), day: day([custom]) }, DATE, "treadmill_hiit_4x4", {
      kind: "replace",
      target: custom,
    });
    expect(bodies).toHaveLength(2);
    expect(bodies[0].dry_run).toBe(true);
    expect(bodies[1].dry_run).toBeUndefined();
    const cached = qc.getQueryData<{ week_plan: WeekPlan }>(queryKeys.week(0));
    expect(cached?.week_plan.weeks[0].days[0].sessions[0].session_id).toBe("treadmill_hiit_4x4");
  });

  it("the dry run does not show it (a custom deleted from My Sessions) → nothing written", async () => {
    const bodies = mockFetch([{ status: 200, body: { dry_run: true, week_plan: plan([]) } }]);
    const qc = new QueryClient();
    const err = await placeOrphanSession(
      qc,
      { weekNum: 0, weekPlan: plan([custom]), day: day([custom]) },
      DATE,
      "custom_cs_gone",
      { kind: "replace", target: custom },
    ).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(OrphanPlacementError);
    expect(bodies).toHaveLength(1);
  });
});

describe("Start: is the session still on that day?", () => {
  function qcWithWeek(sessions: SessionSlot[], updatedAt: number) {
    const qc = new QueryClient();
    qc.setQueryData(queryKeys.week(0), { week_num: 9, week_plan: plan(sessions) }, { updatedAt });
    return qc;
  }

  it("needs a check only online, with a cached week holding the day, older than a minute", () => {
    const now = Date.parse("2026-11-04T11:28:00Z");
    expect(startNeedsPlanCheck(qcWithWeek([], now - 30_000), DATE, now)).toBe(false);
    expect(startNeedsPlanCheck(qcWithWeek([], now - 61_000), DATE, now)).toBe(true);
    expect(startNeedsPlanCheck(new QueryClient(), DATE, now)).toBe(false);
    expect(startNeedsPlanCheck(qcWithWeek([], now - 61_000), "2026-12-01", now)).toBe(false);
    Object.defineProperty(navigator, "onLine", { configurable: true, value: false });
    try {
      expect(startNeedsPlanCheck(qcWithWeek([], now - 61_000), DATE, now)).toBe(false);
    } finally {
      Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
    }
  });

  it("the fresh week no longer has it → false; still there → true", async () => {
    mockFetch([{ status: 200, body: { week_num: 9, week_plan: plan([slot("custom_cs_320de282", "lunch")]) } }]);
    const qc = qcWithWeek([slot("treadmill_hiit_4x4", "lunch")], Date.now() - 120_000);
    expect(await sessionStillPlanned(qc, DATE, "treadmill_hiit_4x4")).toBe(false);

    mockFetch([{ status: 200, body: { week_num: 9, week_plan: plan([slot("treadmill_hiit_4x4", "lunch")]) } }]);
    const qc2 = qcWithWeek([slot("treadmill_hiit_4x4", "lunch")], Date.now() - 120_000);
    expect(await sessionStillPlanned(qc2, DATE, "treadmill_hiit_4x4")).toBe(true);
  });

  it("fail-open: an error or a slow server starts the session", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    }));
    const qc = qcWithWeek([slot("treadmill_hiit_4x4", "lunch")], Date.now() - 120_000);
    expect(await sessionStillPlanned(qc, DATE, "treadmill_hiit_4x4")).toBe(true);

    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));
    const qc2 = qcWithWeek([slot("treadmill_hiit_4x4", "lunch")], Date.now() - 120_000);
    const answer = sessionStillPlanned(qc2, DATE, "treadmill_hiit_4x4");
    await vi.advanceTimersByTimeAsync(START_CHECK_TIMEOUT_MS + 10);
    expect(await answer).toBe(true);
  });
});
