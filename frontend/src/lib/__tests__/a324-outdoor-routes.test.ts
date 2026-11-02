import { describe, expect, it } from "vitest";
import {
  aggregateRoutes,
  routeStyleBadgeClass,
  sessionRouteStyle,
  STYLE_LABEL,
} from "@/lib/outdoor-routes";
import type { OutdoorAttempt, OutdoorSession } from "@/lib/types";

/**
 * A324 — Outdoor History (the routes list and each session's rows) reads a
 * send as `sent` on lead. Before A324 it took any `sent`, so a pitch seconded
 * clean would have shown as a green «flash».
 */

function session(date: string, routes: Array<{ name: string; grade?: string; style?: string; attempts: OutdoorAttempt[] }>): OutdoorSession {
  return {
    log_version: "outdoor.v2",
    date,
    spot_name: "Presles",
    discipline: "lead",
    duration_minutes: 240,
    routes: routes.map((r) => ({ grade: "6b", ...r })) as OutdoorSession["routes"],
  };
}

describe("A324 — sessionRouteStyle", () => {
  it("a lead send keeps the B181 / A227 styles", () => {
    expect(sessionRouteStyle({ attempts: [{ result: "sent" }] })).toBe("flash");
    expect(sessionRouteStyle({ style: "onsight", attempts: [{ result: "sent" }] })).toBe("onsight");
    expect(sessionRouteStyle({ attempts: [{ result: "fell" }, { result: "sent" }] })).toBe("redpoint");
  });

  it("a clean second / top-rope is «second clean» / «TR clean», never a send style", () => {
    expect(sessionRouteStyle({ attempts: [{ result: "sent", rope_role: "second" }] })).toBe("second_clean");
    expect(sessionRouteStyle({ attempts: [{ result: "sent", rope_role: "toprope" }] })).toBe("tr_clean");
    // An explicit onsight on a non-lead ascent is no onsight (critic: never «X (onsight) TR clean»).
    expect(sessionRouteStyle({ style: "onsight", attempts: [{ result: "sent", rope_role: "toprope" }] })).toBe("tr_clean");
    expect(STYLE_LABEL.second_clean).toBe("second clean");
    expect(STYLE_LABEL.tr_clean).toBe("TR clean");
  });

  it("an A0 alone is «A0»; falls only are «projecting»", () => {
    expect(sessionRouteStyle({ attempts: [{ result: "aid" }] })).toBe("aid");
    expect(sessionRouteStyle({ attempts: [{ result: "fell" }, { result: "fell", rope_role: "toprope" }] })).toBe("project");
    expect(STYLE_LABEL.aid).toBe("A0");
  });

  it("a top-rope try then a lead send is a redpoint, not a flash", () => {
    expect(
      sessionRouteStyle({ attempts: [{ result: "sent", rope_role: "toprope" }, { result: "sent" }] }),
    ).toBe("redpoint");
  });

  it("green only for a lead send, blue for clean non-lead, amber for A0", () => {
    expect(routeStyleBadgeClass("flash")).toContain("success");
    expect(routeStyleBadgeClass("second_clean")).toContain("info");
    expect(routeStyleBadgeClass("tr_clean")).toContain("info");
    expect(routeStyleBadgeClass("second_clean")).not.toContain("success");
    expect(routeStyleBadgeClass("aid")).toContain("warning");
    expect(routeStyleBadgeClass("project")).toBe("text-muted-foreground");
  });
});

describe("A324 — aggregateRoutes", () => {
  it("only seconded clean → not sent, «second clean»", () => {
    const [r] = aggregateRoutes([
      session("2026-10-31", [{ name: "Cancer (Presles) – L1", attempts: [{ result: "sent", rope_role: "second" }] }]),
    ]);
    expect(r.isSent).toBe(false);
    expect(r.attemptsToSend).toBeNull();
    expect(r.bestStyle).toBe("second_clean");
  });

  it("top-rope on day 1, led clean on day 2 → redpoint in 2 tries", () => {
    const [r] = aggregateRoutes([
      session("2026-11-01", [{ name: "Cernes", attempts: [{ result: "sent", rope_role: "toprope" }] }]),
      session("2026-11-08", [{ name: "Cernes", attempts: [{ result: "sent" }] }]),
    ]);
    expect(r.isSent).toBe(true);
    expect(r.attemptsToSend).toBe(2);
    expect(r.bestStyle).toBe("redpoint");
    expect(r.totalSessions).toBe(2);
  });

  it("A0 only → «A0», not sent", () => {
    const [r] = aggregateRoutes([
      session("2026-10-31", [{ name: "Cancer (Presles) – L8", grade: "7b", attempts: [{ result: "aid" }] }]),
    ]);
    expect(r.isSent).toBe(false);
    expect(r.bestStyle).toBe("aid");
  });

  it("logs without rope_role read exactly as before (lead)", () => {
    const [flash, project] = aggregateRoutes([
      session("2026-10-10", [
        { name: "A", attempts: [{ result: "sent" }] },
        { name: "B", attempts: [{ result: "topped_out" }, { result: "fell" }] },
      ]),
    ]);
    expect(flash.bestStyle).toBe("flash");
    expect(flash.isSent).toBe(true);
    expect(project.bestStyle).toBe("project");
    expect(project.isSent).toBe(false);
  });
});
