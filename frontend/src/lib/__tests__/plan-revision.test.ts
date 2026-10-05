import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

import {
  STALE_PLAN_MESSAGE,
  emitStalePlan,
  isRetrySafeEvents,
  onStalePlan,
  parseStalePlanBody,
  withBaseRevision,
} from "@/lib/plan-revision";
import {
  ApiError,
  StalePlanError,
  addExerciseToSession,
  apiErrorDetail,
  applyEvents,
  applyOverride,
} from "@/lib/api";
import type { WeekPlan } from "@/lib/types";

/**
 * B371 — the client half of the plan_revision check.
 *
 * Before B371 a write shipped the whole week plan with no version: a copy that
 * another device had made obsolete overwrote the newer plan in silence. Every
 * write now sends `base_revision`; a 409 refetches the week (watcher) and only
 * an idempotent action is re-sent by itself.
 */

function plan(rev: number, sessions: Array<Record<string, unknown>> = [], extraDay: Record<string, unknown> = {}): WeekPlan {
  return {
    start_date: "2026-10-12",
    plan_revision: rev,
    weeks: [{ days: [{ date: "2026-10-13", sessions, ...extraDay } as never] }],
  } as WeekPlan;
}

const pending = { session_id: "strength_long", slot: "evening", status: "planned" };
const done = { ...pending, status: "done" };

describe("parseStalePlanBody", () => {
  it("recognises the server's 409 body", () => {
    const body = parseStalePlanBody(JSON.stringify({
      detail: "x", code: "stale_plan", current_revision: 7, week_start: "2026-10-12", week_plan: plan(7),
    }));
    expect(body?.current_revision).toBe(7);
    expect(body?.week_plan?.plan_revision).toBe(7);
  });
  it("ignores other 409s (immutability of a done session) and garbage", () => {
    expect(parseStalePlanBody(JSON.stringify({ detail: "Cannot modify session with status 'done'" }))).toBeNull();
    expect(parseStalePlanBody("not json")).toBeNull();
  });
});

describe("withBaseRevision", () => {
  it("sends the revision of the plan being edited", () => {
    expect(withBaseRevision({ week_plan: plan(4) }).base_revision).toBe(4);
  });
  it("sends null for a plan without one (server treats it as a legacy client)", () => {
    expect(withBaseRevision({ week_plan: { weeks: [] } as WeekPlan }).base_revision).toBeNull();
  });
});

describe("isRetrySafeEvents", () => {
  it("mark_done on a session still pending on the fresh plan is safe", () => {
    expect(isRetrySafeEvents([{ event_type: "mark_done", date: "2026-10-13", session_ref: "strength_long" }], plan(3, [pending]))).toBe(true);
  });
  it("not when the other device already marked it (would double the completion log)", () => {
    expect(isRetrySafeEvents([{ event_type: "mark_done", date: "2026-10-13", session_ref: "strength_long" }], plan(3, [done]))).toBe(false);
  });
  it("not when the session is gone from the fresh plan (moved / removed)", () => {
    expect(isRetrySafeEvents([{ event_type: "mark_skipped", date: "2026-10-13", session_ref: "strength_long" }], plan(3, []))).toBe(false);
  });
  it("set_outdoor_plan only on a still-open outdoor day", () => {
    const ev = [{ event_type: "set_outdoor_plan", date: "2026-10-13", plan: null }];
    expect(isRetrySafeEvents(ev, plan(3, [], { outdoor_spot_name: "Arco" }))).toBe(true);
    expect(isRetrySafeEvents(ev, plan(3, [], { outdoor_spot_name: "Arco", outdoor_session_status: "done" }))).toBe(false);
    expect(isRetrySafeEvents(ev, plan(3, []))).toBe(false);
  });
  it("anything that depends on the plan it was decided on is never retried", () => {
    for (const t of ["move_session", "remove_session", "mark_planned", "add_custom_session", "change_gym"]) {
      expect(isRetrySafeEvents([{ event_type: t, date: "2026-10-13" }], plan(3, [pending]))).toBe(false);
    }
    expect(isRetrySafeEvents([], plan(3, [pending]))).toBe(false);
    expect(isRetrySafeEvents([{ event_type: "mark_done", date: "2026-10-13" }], null)).toBe(false);
  });
});

describe("onStalePlan", () => {
  it("delivers every conflict to subscribers until they unsubscribe", () => {
    const seen: boolean[] = [];
    const off = onStalePlan((e) => seen.push(e.retried));
    emitStalePlan({ retried: false });
    emitStalePlan({ retried: true });
    off();
    emitStalePlan({ retried: false });
    expect(seen).toEqual([false, true]);
  });
});

// ---------------------------------------------------------------------------
// api.ts — request bodies and the 409 path
// ---------------------------------------------------------------------------

type Call = { url: string; body: Record<string, unknown> };

function mockFetch(responses: Array<{ status: number; body: unknown }>) {
  const calls: Call[] = [];
  const fn = vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, body: JSON.parse(String(init?.body ?? "{}")) });
    const r = responses.shift();
    if (!r) throw new Error("unexpected fetch");
    return new Response(JSON.stringify(r.body), { status: r.status, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fn);
  return calls;
}

function stale409(rev: number, current: WeekPlan) {
  return { status: 409, body: { detail: "stale", code: "stale_plan", current_revision: rev, week_start: "2026-10-12", week_plan: current } };
}

describe("api writes carry base_revision and handle 409", () => {
  let events: Array<{ retried: boolean }>;
  let off: () => void;
  beforeEach(() => {
    events = [];
    off = onStalePlan((e) => events.push({ retried: e.retried }));
  });
  afterEach(() => {
    off();
    vi.unstubAllGlobals();
  });

  it("every write sends the revision it edits", async () => {
    const calls = mockFetch([
      { status: 200, body: { week_plan: plan(5) } },
      { status: 200, body: { week_plan: plan(6) } },
      { status: 200, body: { week_plan: plan(7) } },
    ]);
    await applyEvents({ events: [{ event_type: "move_session" }], week_plan: plan(4) });
    await applyOverride({ intent: "rest", location: "home", reference_date: "2026-10-13", week_plan: plan(5) });
    await addExerciseToSession({ date: "2026-10-13", session_index: 0, exercise_id: "x", week_plan: plan(6) });
    expect(calls.map((c) => c.body.base_revision)).toEqual([4, 5, 6]);
  });

  it("a safe action is re-sent once on the fresh plan, and the watcher hears 'retried'", async () => {
    const fresh = plan(9, [pending]);
    const calls = mockFetch([stale409(9, fresh), { status: 200, body: { week_plan: plan(10, [done]) } }]);
    const res = await applyEvents({
      events: [{ event_type: "mark_done", date: "2026-10-13", session_ref: "strength_long" }],
      week_plan: plan(8, [pending]),
    });
    expect(res.week_plan.plan_revision).toBe(10);
    expect(calls).toHaveLength(2);
    expect(calls[1].body.base_revision).toBe(9);
    expect((calls[1].body.week_plan as WeekPlan).plan_revision).toBe(9);
    expect(events).toEqual([{ retried: true }]);
  });

  it("an unsafe action is not re-sent: StalePlanError, watcher told, nothing retried", async () => {
    const calls = mockFetch([stale409(9, plan(9, [pending]))]);
    const err = await applyEvents({
      events: [{ event_type: "move_session", from_date: "2026-10-13", from_slot: "evening", to_date: "2026-10-14", to_slot: "evening" }],
      week_plan: plan(8, [pending]),
    }).catch((e) => e);
    expect(err).toBeInstanceOf(StalePlanError);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as StalePlanError).status).toBe(409);
    expect((err as StalePlanError).currentRevision).toBe(9);
    expect((err as Error).message).toBe(STALE_PLAN_MESSAGE);
    expect(apiErrorDetail(err, "fallback")).toBe(STALE_PLAN_MESSAGE);
    expect(calls).toHaveLength(1);
    expect(events).toEqual([{ retried: false }]);
  });

  it("a retry that is itself stale is not retried again", async () => {
    const calls = mockFetch([stale409(9, plan(9, [pending])), stale409(10, plan(10, [pending]))]);
    const err = await applyEvents({
      events: [{ event_type: "mark_done", date: "2026-10-13", session_ref: "strength_long" }],
      week_plan: plan(8, [pending]),
    }).catch((e) => e);
    expect(err).toBeInstanceOf(StalePlanError);
    expect(calls).toHaveLength(2);
    expect(events).toEqual([{ retried: false }]);
  });

  it("a non-replanner write (override) is never retried", async () => {
    const calls = mockFetch([stale409(9, plan(9, [pending]))]);
    const err = await applyOverride({ intent: "rest", location: "home", reference_date: "2026-10-13", week_plan: plan(8) }).catch((e) => e);
    expect(err).toBeInstanceOf(StalePlanError);
    expect(calls).toHaveLength(1);
    expect(events).toEqual([{ retried: false }]);
  });

  it("other 409s stay plain ApiErrors and do not reach the watcher", async () => {
    mockFetch([{ status: 409, body: { detail: "Cannot modify session with status 'done' on 2026-10-13" } }]);
    const err = await addExerciseToSession({ date: "2026-10-13", session_index: 0, exercise_id: "x", week_plan: plan(3) }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).not.toBeInstanceOf(StalePlanError);
    expect(events).toEqual([]);
  });

  it("a dry run is sent as is and never retried", async () => {
    const calls = mockFetch([{ status: 200, body: { week_plan: plan(3), dry_run: true, key_conflicts: [] } }]);
    await applyEvents({ events: [{ event_type: "move_session" }], week_plan: plan(3), dry_run: true });
    expect(calls).toHaveLength(1);
  });
});
