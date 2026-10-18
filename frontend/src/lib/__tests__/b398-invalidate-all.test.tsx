/**
 * @vitest-environment jsdom
 *
 * B398 (O13) — `invalidateAll` (a reset / import of the user's data) used to be
 * `qc.clear()`: the immutable catalog and the subscription status went too,
 * so 2-4 requests fetched again what had not changed and the TrialBanner
 * flickered. It now removes only the queries built from the user's data.
 *
 * What must NOT change: a sign-out or an account switch still empties the
 * whole cache (A245 B-2, privacy on a shared device). That path is
 * `SessionScopeGuard`, which calls `qc.clear()` itself — pinned below.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createElement, type ReactNode } from "react";
import { render, cleanup, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const { auth } = vi.hoisted(() => ({
  auth: { isLoaded: true, userId: "user_A" as string | null },
}));

vi.mock("@clerk/nextjs", () => ({ useAuth: () => auth }));

import { invalidateAll, DATA_INDEPENDENT_ROOTS } from "@/lib/invalidation";
import { queryKeys } from "@/lib/query-keys";
import { SessionScopeGuard } from "@/components/session-scope-guard";

const USER_DATA_KEYS: ReadonlyArray<readonly unknown[]> = [
  queryKeys.state,
  queryKeys.stateStatus,
  queryKeys.week(0),
  queryKeys.week(7),
  queryKeys.sessionResolve("s1"),
  queryKeys.outdoorSpots,
  queryKeys.outdoorSessions("2026-10-01"),
  queryKeys.freeSessionHistory("2026-10-17"),
  queryKeys.reportsWeekly("2026-10-12"),
  queryKeys.milestones,
  queryKeys.customSessions,
  queryKeys.gradeEvidence,
  queryKeys.tipsDaily("2026-10-17"),
];

const DATA_INDEPENDENT_KEYS: ReadonlyArray<readonly unknown[]> = [
  queryKeys.catalogSessions,
  queryKeys.catalogExercises,
  queryKeys.subscriptionStatus,
  queryKeys.onboardingDefaults,
];

let qc: QueryClient;

function seedEverything() {
  for (const key of [...USER_DATA_KEYS, ...DATA_INDEPENDENT_KEYS]) {
    qc.setQueryData(key, { seeded: true });
  }
}

beforeEach(() => {
  qc = new QueryClient();
  auth.isLoaded = true;
  auth.userId = "user_A";
});

afterEach(cleanup);

describe("B398 O13 — invalidateAll removes the user's data, keeps the rest", () => {
  it("drops every query built from the user's data", () => {
    seedEverything();
    invalidateAll(qc);
    for (const key of USER_DATA_KEYS) {
      expect(qc.getQueryData(key), JSON.stringify(key)).toBeUndefined();
    }
  });

  it("keeps the catalog, the subscription and the onboarding defaults", () => {
    seedEverything();
    invalidateAll(qc);
    for (const key of DATA_INDEPENDENT_KEYS) {
      expect(qc.getQueryData(key), JSON.stringify(key)).toEqual({ seeded: true });
    }
    expect(qc.getQueryCache().getAll()).toHaveLength(DATA_INDEPENDENT_KEYS.length);
  });

  it("the kept roots are exactly those three", () => {
    expect([...DATA_INDEPENDENT_ROOTS].sort()).toEqual(["catalog", "onboarding", "subscription"]);
  });
});

describe("B398 O13 — sign-out and account switch still clear EVERYTHING", () => {
  function renderGuard() {
    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client: qc }, children);
    return render(createElement(SessionScopeGuard), { wrapper });
  }

  it("sign-out empties the whole cache, subscription and catalog included", () => {
    const view = renderGuard();
    seedEverything();
    auth.userId = null;
    act(() => view.rerender(createElement(SessionScopeGuard)));
    expect(qc.getQueryCache().getAll()).toHaveLength(0);
  });

  it("an account switch empties the whole cache", () => {
    const view = renderGuard();
    seedEverything();
    auth.userId = "user_B";
    act(() => view.rerender(createElement(SessionScopeGuard)));
    expect(qc.getQueryCache().getAll()).toHaveLength(0);
  });

  it("the same user staying signed in keeps the cache", () => {
    const view = renderGuard();
    seedEverything();
    act(() => view.rerender(createElement(SessionScopeGuard)));
    expect(qc.getQueryCache().getAll().length).toBe(USER_DATA_KEYS.length + DATA_INDEPENDENT_KEYS.length);
  });
});
