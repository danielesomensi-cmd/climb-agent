/**
 * @vitest-environment jsdom
 *
 * B396 review — the daily quote is persisted (query-persist 'quotes') with a
 * 24 h staleTime. Keyed by context only, the copy restored on the next
 * morning's open was still "fresh": /today showed yesterday's quote. The
 * client-local day is now part of the key, and the request carries the same
 * day: the server's today is UTC, so between local midnight and UTC midnight
 * it would otherwise fill today's key with yesterday's quote.
 *
 * The daily tip was checked for the same problem: its key already carries the
 * date it is asked for.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { createElement, type ReactNode } from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const { getDailyQuote } = vi.hoisted(() => ({ getDailyQuote: vi.fn() }));
vi.mock("@/lib/api", () => ({
  getDailyQuote: (context?: string, date?: string) => getDailyQuote(context, date),
  getDailyTip: vi.fn(),
  getMilestones: vi.fn(),
  getMonthlyHeatmap: vi.fn(),
  getOnboardingDefaults: vi.fn(),
  getWeeklyReport: vi.fn(),
  getSuggestedSessions: vi.fn(),
}));

import { useDailyQuote } from "@/lib/hooks/queries/use-misc";
import { queryKeys } from "@/lib/query-keys";
import { PERSISTED_QUERY_PREFIXES } from "@/lib/query-persist";

const YESTERDAY_QUOTE = { id: "q-1", text: "Yesterday's quote", author: "A" };
const TODAY_QUOTE = { id: "q-2", text: "Today's quote", author: "B" };

let qc: QueryClient;
function wrapper({ children }: { children: ReactNode }) {
  return createElement(QueryClientProvider, { client: qc }, children);
}

beforeEach(() => {
  vi.clearAllMocks();
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.useFakeTimers({ toFake: ["Date"] });
});

afterEach(() => vi.useRealTimers());

describe("daily quote cache key", () => {
  it("carries the client-local day", () => {
    expect(queryKeys.quotesDaily("general", "2026-10-18")).toEqual(["quotes", "daily", "general", "2026-10-18"]);
    // Still under the persisted 'quotes' prefix.
    expect(PERSISTED_QUERY_PREFIXES).toContain("quotes");
  });

  it("a quote restored from yesterday (still inside its 24 h) is not shown today", async () => {
    // Fetched at 23:50 on the 17th, persisted, restored at 07:00 on the 18th:
    // 7 h 10 min old, well inside the 24 h staleTime.
    vi.setSystemTime(new Date(2026, 9, 17, 23, 50));
    qc.setQueryData(queryKeys.quotesDaily("general", "2026-10-17"), YESTERDAY_QUOTE, {
      updatedAt: Date.now(),
    });
    vi.setSystemTime(new Date(2026, 9, 18, 7, 0));
    getDailyQuote.mockResolvedValue(TODAY_QUOTE);

    const { result } = renderHook(() => useDailyQuote("general"), { wrapper });
    await waitFor(() => expect(result.current.data).toEqual(TODAY_QUOTE));
    expect(getDailyQuote).toHaveBeenCalledTimes(1);
    expect(getDailyQuote).toHaveBeenCalledWith("general", "2026-10-18");
  });

  it("just after local midnight the request asks for the local day, not the server's UTC one", async () => {
    // 00:30 in Rome on the 19th is still the 18th in UTC on Railway.
    vi.setSystemTime(new Date(2026, 9, 19, 0, 30));
    getDailyQuote.mockResolvedValue(TODAY_QUOTE);
    renderHook(() => useDailyQuote("general"), { wrapper });
    await waitFor(() => expect(getDailyQuote).toHaveBeenCalledWith("general", "2026-10-19"));
  });

  it("within the same day the restored quote is served without a request", async () => {
    vi.setSystemTime(new Date(2026, 9, 18, 7, 0));
    qc.setQueryData(queryKeys.quotesDaily("general", "2026-10-18"), TODAY_QUOTE, { updatedAt: Date.now() });
    vi.setSystemTime(new Date(2026, 9, 18, 21, 0));

    const { result } = renderHook(() => useDailyQuote("general"), { wrapper });
    expect(result.current.data).toEqual(TODAY_QUOTE);
    expect(getDailyQuote).not.toHaveBeenCalled();
  });
});

describe("daily tip cache key (checked, already dated)", () => {
  it("carries the date the tip is asked for", () => {
    expect(queryKeys.tipsDaily("2026-10-18")).toEqual(["tips", "daily", "2026-10-18"]);
  });
});
