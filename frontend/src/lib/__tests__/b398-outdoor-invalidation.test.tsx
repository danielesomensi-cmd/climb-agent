/**
 * @vitest-environment jsdom
 *
 * B398 (O1) — on /week, after logging or editing an outdoor day the card kept
 * the old routes. The routes come from `useOutdoorDoneDays` →
 * `['outdoor','sessions',since]`, but the success handlers refreshed only the
 * weeks (log) or state + week + resolved sessions (edit, `refetchAll`): the
 * outdoor list stayed cached for its 60 s staleTime. They now go through
 * `invalidateOutdoor`, which refreshes the outdoor keys AND the weeks (B371:
 * the log moves the week's revision) — and no longer state nor the resolves.
 *
 * Also pinned here: O5 (the log target's two reads run in parallel) and O11
 * (the spots come from the React Query cache).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createElement, type ReactNode } from "react";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { stripComments } from "./helpers/source-scan";

const { ApiError, getOutdoorSessions, getOutdoorSpots, getOutdoorLogByDate } = vi.hoisted(() => {
  class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.name = "ApiError";
      this.status = status;
    }
  }
  return {
    ApiError,
    getOutdoorSessions: vi.fn(),
    getOutdoorSpots: vi.fn(),
    getOutdoorLogByDate: vi.fn(),
  };
});

vi.mock("@/lib/api", () => ({
  ApiError,
  getOutdoorSessions: (since?: string) => getOutdoorSessions(since),
  getOutdoorSpots: () => getOutdoorSpots(),
  getOutdoorLogByDate: (d: string) => getOutdoorLogByDate(d),
  getOutdoorStats: vi.fn(),
}));

import { useOutdoorDoneDays } from "@/lib/hooks/queries/use-outdoor-sessions";
import { fetchOutdoorSpots } from "@/lib/hooks/queries/use-outdoor";
import { invalidateOutdoor } from "@/lib/invalidation";
import { resolveOutdoorLogTarget } from "@/lib/outdoor-log-target";
import { queryKeys } from "@/lib/query-keys";

const DAY = "2026-10-17";
const route = (name: string) => ({ name, grade: "7a", attempts: [{ result: "send" }] });

let qc: QueryClient;
function wrapper({ children }: { children: ReactNode }) {
  return createElement(QueryClientProvider, { client: qc }, children);
}

beforeEach(() => {
  vi.clearAllMocks();
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
});

describe("B398 O1 — the /week routes follow an outdoor log or edit", () => {
  async function mountWithRoutes() {
    getOutdoorSessions.mockResolvedValue({
      sessions: [{ date: DAY, spot_name: "Arco", routes: [route("Old line")] }],
    });
    const hook = renderHook(() => useOutdoorDoneDays([DAY]), { wrapper });
    await waitFor(() => expect(hook.result.current.routesMap[DAY]).toHaveLength(1));
    // The user edits the day: the server now has two routes.
    getOutdoorSessions.mockResolvedValue({
      sessions: [{ date: DAY, spot_name: "Arco", routes: [route("Old line"), route("New line")] }],
    });
    return hook;
  }

  it("the old refresh (state + week + resolves) left the routes stale — the bug", async () => {
    const hook = await mountWithRoutes();
    await act(async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: queryKeys.state }),
        qc.invalidateQueries({ queryKey: queryKeys.week(0) }),
        qc.invalidateQueries({ queryKey: queryKeys.sessionResolveAll }),
      ]);
    });
    expect(getOutdoorSessions).toHaveBeenCalledTimes(1);
    expect(hook.result.current.routesMap[DAY].map((r) => r.name)).toEqual(["Old line"]);
  });

  it("invalidateOutdoor refetches the outdoor sessions: the card shows the new route", async () => {
    const hook = await mountWithRoutes();
    await act(async () => {
      await invalidateOutdoor(qc);
    });
    expect(getOutdoorSessions).toHaveBeenCalledTimes(2);
    await waitFor(() =>
      expect(hook.result.current.routesMap[DAY].map((r) => r.name)).toEqual(["Old line", "New line"]),
    );
  });

  it("invalidateOutdoor marks outdoor + weeks stale, not the state nor the resolved sessions", async () => {
    const seed = (key: readonly unknown[]) => qc.setQueryData(key, { seeded: true });
    seed(queryKeys.outdoorSessions(DAY));
    seed(queryKeys.outdoorStats());
    seed(queryKeys.week(0));
    seed(queryKeys.week(7));
    seed(queryKeys.state);
    seed(queryKeys.sessionResolve("s1"));
    await invalidateOutdoor(qc);
    const stale = (key: readonly unknown[]) => qc.getQueryState(key)?.isInvalidated;
    expect(stale(queryKeys.outdoorSessions(DAY))).toBe(true);
    expect(stale(queryKeys.outdoorStats())).toBe(true);
    expect(stale(queryKeys.week(0))).toBe(true);
    expect(stale(queryKeys.week(7))).toBe(true);
    expect(stale(queryKeys.state)).toBe(false);
    expect(stale(queryKeys.sessionResolve("s1"))).toBe(false);
  });

  it("the /week success handlers go through the outdoor invalidation", () => {
    const code = stripComments(
      readFileSync(join(process.cwd(), "src/app/(main)/week/page.tsx"), "utf8"),
    );
    const body = (name: string) => {
      const start = code.indexOf(`async function ${name}(`);
      expect(start, `${name} not found`).toBeGreaterThan(-1);
      return code.slice(start, code.indexOf("\n  }\n", start));
    };
    const log = body("handleOutdoorLogSuccess");
    expect(log).toContain("invalidateOutdoor(qc)");
    // Not synced: the week is written from the events response, the outdoor
    // list still has to refetch.
    expect(log).toContain("queryKeys.outdoorAll");
    const edit = body("handleEditOutdoorSuccess");
    expect(edit).toContain("invalidateOutdoor(qc)");
    expect(edit).not.toContain("refetchAll");
  });
});

describe("B398 O5 — the log target's two reads run in parallel", () => {
  it("asks for today's log before the spots have answered", async () => {
    let releaseSpots: (v: { spots: never[] }) => void = () => {};
    const loadSpots = vi.fn(
      () => new Promise<{ spots: never[] }>((resolve) => { releaseSpots = resolve; }),
    );
    getOutdoorLogByDate.mockRejectedValue(new ApiError(404, "none"));

    const pending = resolveOutdoorLogTarget(DAY, loadSpots);
    // In series the log GET waited for the spots; now both are in flight.
    expect(loadSpots).toHaveBeenCalledTimes(1);
    expect(getOutdoorLogByDate).toHaveBeenCalledWith(DAY);
    releaseSpots({ spots: [] });
    expect((await pending).kind).toBe("new");
  });
});

describe("B398 O11 — outdoor spots from the React Query cache", () => {
  it("a second read within the staleTime makes no request", async () => {
    getOutdoorSpots.mockResolvedValue({ spots: [{ id: "s1", name: "Arco", discipline: "lead" }] });
    const first = await fetchOutdoorSpots(qc);
    const second = await fetchOutdoorSpots(qc);
    expect(getOutdoorSpots).toHaveBeenCalledTimes(1);
    expect(second).toEqual(first);
    // Same key as useOutdoorSpots and the add / delete mutations.
    expect(qc.getQueryData(queryKeys.outdoorSpots)).toEqual(first);
  });
});
