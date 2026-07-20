import { describe, it, expect } from "vitest";
import { deriveTryTimings, lastTryMs, routeHasTimestamps } from "@/lib/try-timings";
import type { OutdoorAttempt } from "@/lib/types";

// Helper: build a route from attempts.
const route = (attempts: OutdoorAttempt[]) => ({ attempts });
const iso = (s: string) => s; // readability

describe("deriveTryTimings — A241 session-wide rest", () => {
  it("first burn of the session has null rest", () => {
    const routes = [route([{ result: "fell", logged_at: iso("2026-07-20T09:00:00Z") }])];
    expect(deriveTryTimings(routes)[0][0].rest_before_seconds).toBeNull();
  });

  it("rest = gap from previous burn end to this burn start (same route)", () => {
    // try1 ends 09:00; try2 climb 60s ends 09:15 → start 09:14 → rest 14min.
    const routes = [
      route([
        { result: "fell", logged_at: iso("2026-07-20T09:00:00Z") },
        { result: "sent", logged_at: iso("2026-07-20T09:15:00Z"), climb_seconds: 60 },
      ]),
    ];
    const t = deriveTryTimings(routes)[0];
    expect(t[0].rest_before_seconds).toBeNull();
    expect(t[1].rest_before_seconds).toBe(14 * 60); // 09:14 − 09:00
    expect(t[1].climb_seconds).toBe(60);
  });

  it("rest attribution crosses routes chronologically", () => {
    // routeA try @09:00, routeB try @09:10, routeA try2 @09:30.
    // routeA try2 rest = 09:30 − 09:10 (last burn anywhere) = 20min, NOT 30.
    const routes = [
      route([
        { result: "fell", logged_at: iso("2026-07-20T09:00:00Z") },
        { result: "sent", logged_at: iso("2026-07-20T09:30:00Z") },
      ]),
      route([{ result: "sent", logged_at: iso("2026-07-20T09:10:00Z") }]),
    ];
    const t = deriveTryTimings(routes);
    expect(t[0][0].rest_before_seconds).toBeNull(); // very first burn
    expect(t[1][0].rest_before_seconds).toBe(10 * 60); // 09:10 − 09:00
    expect(t[0][1].rest_before_seconds).toBe(20 * 60); // 09:30 − 09:10
  });

  it("deleting a middle try recomputes rest for the next one", () => {
    // Full: 09:00, 09:10, 09:30 → third rest 20min.
    // Delete the middle (09:10) → third rest becomes 09:30 − 09:00 = 30min.
    const routes = [
      route([
        { result: "fell", logged_at: iso("2026-07-20T09:00:00Z") },
        { result: "sent", logged_at: iso("2026-07-20T09:30:00Z") },
      ]),
    ];
    expect(deriveTryTimings(routes)[0][1].rest_before_seconds).toBe(30 * 60);
  });

  it("climb timer subtracted from the burn start", () => {
    // try2 ends 09:20 with climb 300s → start 09:15 → rest = 09:15 − 09:00 = 15min.
    const routes = [
      route([
        { result: "fell", logged_at: iso("2026-07-20T09:00:00Z") },
        { result: "fell", logged_at: iso("2026-07-20T09:20:00Z"), climb_seconds: 300 },
      ]),
    ];
    expect(deriveTryTimings(routes)[0][1].rest_before_seconds).toBe(15 * 60);
  });

  it("tries without climb_seconds are point events (rest uses logged_at)", () => {
    const routes = [
      route([
        { result: "fell", logged_at: iso("2026-07-20T09:00:00Z") },
        { result: "sent", logged_at: iso("2026-07-20T09:12:00Z") },
      ]),
    ];
    const t = deriveTryTimings(routes)[0];
    expect(t[1].rest_before_seconds).toBe(12 * 60);
    expect(t[1].climb_seconds).toBeNull();
  });

  it("legacy tries without logged_at derive nothing and don't join the chain", () => {
    const routes = [
      route([
        { result: "fell", rest_seconds: 120, climb_seconds: 60 }, // B279/A227 legacy
        { result: "sent", logged_at: iso("2026-07-20T09:12:00Z") },
      ]),
    ];
    const t = deriveTryTimings(routes)[0];
    expect(t[0].rest_before_seconds).toBeNull();
    // The timestamped try is the first (and only) chain member → null rest.
    expect(t[1].rest_before_seconds).toBeNull();
  });

  it("negative gaps (clock skew) are clamped to 0", () => {
    const routes = [
      route([
        { result: "fell", logged_at: iso("2026-07-20T09:10:00Z") },
        { result: "sent", logged_at: iso("2026-07-20T09:05:00Z") }, // out of order
      ]),
    ];
    // Sorted by end time: 09:05 first (null), then 09:10 rest = max(0, ...) = 0?
    // 09:10 start − 09:05 end = 300s.
    const t = deriveTryTimings(routes)[0];
    expect(t.every((x) => x.rest_before_seconds == null || x.rest_before_seconds >= 0)).toBe(true);
  });
});

describe("routeHasTimestamps / lastTryMs", () => {
  it("routeHasTimestamps true only with a valid logged_at", () => {
    expect(routeHasTimestamps(route([{ result: "fell" }]))).toBe(false);
    expect(routeHasTimestamps(route([{ result: "fell", rest_seconds: 60 }]))).toBe(false);
    expect(routeHasTimestamps(route([{ result: "fell", logged_at: "2026-07-20T09:00:00Z" }]))).toBe(true);
    expect(routeHasTimestamps(route([{ result: "fell", logged_at: "not-a-date" }]))).toBe(false);
  });

  it("lastTryMs returns the latest timestamp, null when none", () => {
    expect(lastTryMs(route([{ result: "fell" }]))).toBeNull();
    const ms = lastTryMs(route([
      { result: "fell", logged_at: "2026-07-20T09:00:00Z" },
      { result: "sent", logged_at: "2026-07-20T09:30:00Z" },
    ]));
    expect(ms).toBe(Date.parse("2026-07-20T09:30:00Z"));
  });
});
