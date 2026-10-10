/**
 * A309 — "Start" on a saved custom session, and the picker's double-add guard.
 *
 * Start opens /session-builder/[id]/play?date=today. That player logs the
 * session by marking `custom_<id>` done on that date of the week plan, so the
 * session must be on today's plan first: `decideCustomStart` says whether to
 * play straight away, insert it in a free slot first, or stop.
 */

import { describe, it, expect } from "vitest";
import { decideCustomStart, playHref } from "../start-custom-session";
import { pickerTapAction } from "../exercise-picker";
import type { DayPlan, SessionSlot } from "@/lib/types";

const slot = (s: Partial<SessionSlot>): SessionSlot =>
  ({ session_id: "strength_long", location: "gym", slot: "evening", status: "planned", ...s }) as SessionSlot;

const day = (sessions: SessionSlot[], extra: Partial<DayPlan> = {}): DayPlan =>
  ({ date: "2026-10-10", weekday: "saturday", sessions, ...extra }) as DayPlan;

describe("decideCustomStart", () => {
  it("plays straight away when the session is already planned today", () => {
    const d = day([slot({ session_id: "custom_abc", custom_session_id: "abc", is_custom: true, slot: "lunch" })]);
    expect(decideCustomStart(d, "abc")).toEqual({ kind: "play" });
  });

  it("recognises the session by session_ref alone", () => {
    const d = day([slot({ session_id: "custom_abc", slot: "morning" })]);
    expect(decideCustomStart(d, "abc")).toEqual({ kind: "play" });
  });

  it("does not add a second copy of a session already done today", () => {
    const d = day([slot({ session_id: "custom_abc", custom_session_id: "abc", status: "done" })]);
    expect(decideCustomStart(d, "abc")).toEqual({ kind: "already_done" });
  });

  it("inserts in the first free slot otherwise (evening first)", () => {
    expect(decideCustomStart(day([]), "abc")).toEqual({ kind: "insert", slot: "evening" });
    expect(decideCustomStart(day([slot({ slot: "evening" })]), "abc")).toEqual({ kind: "insert", slot: "morning" });
  });

  it("another custom session on the day is not this one", () => {
    const d = day([slot({ session_id: "custom_xyz", custom_session_id: "xyz", slot: "evening" })]);
    expect(decideCustomStart(d, "abc")).toEqual({ kind: "insert", slot: "morning" });
  });

  it("stops on a full day and when today is not in the plan", () => {
    const full = day([slot({ slot: "evening" }), slot({ slot: "morning" }), slot({ slot: "lunch" })]);
    expect(decideCustomStart(full, "abc")).toEqual({ kind: "full" });
    expect(decideCustomStart(null, "abc")).toEqual({ kind: "no_day" });
  });

  it("the player URL carries the date it logs against", () => {
    expect(playHref("abc", "2026-10-10")).toBe("/session-builder/abc/play?date=2026-10-10");
  });
});

describe("pickerTapAction", () => {
  it("adds an exercise not yet in the session", () => {
    expect(pickerTapAction(new Set(["a"]), "b")).toBe("add");
  });

  it("asks before adding a duplicate", () => {
    expect(pickerTapAction(new Set(["a", "b"]), "b")).toBe("confirm");
  });
});
