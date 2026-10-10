import { describe, it, expect } from "vitest";
import {
  adhocCardDate,
  dayDividers,
  dayLabel,
  dropFailedUserTurn,
  isRetryableStatus,
  isStaleAdhocCard,
  localDateOf,
  requestBefore,
} from "../coach-chat";

/** An ISO instant for LOCAL `y-m-d hh:mm` (independent of the runner's TZ). */
const at = (y: number, m: number, d: number, hh = 12, mm = 0) =>
  new Date(y, m - 1, d, hh, mm).toISOString();

describe("A310 — localDateOf", () => {
  it("returns the client-local day of an instant", () => {
    expect(localDateOf(at(2026, 10, 10, 0, 30))).toBe("2026-10-10");
    expect(localDateOf(at(2026, 10, 9, 23, 59))).toBe("2026-10-09");
  });
  it("is null for missing or bad input", () => {
    expect(localDateOf(undefined)).toBeNull();
    expect(localDateOf("")).toBeNull();
    expect(localDateOf("not a date")).toBeNull();
  });
});

describe("A310 — dayLabel", () => {
  const today = "2026-10-10"; // a Saturday
  it("names today and yesterday", () => {
    expect(dayLabel("2026-10-10", today)).toBe("Today");
    expect(dayLabel("2026-10-09", today)).toBe("Yesterday");
  });
  it("formats older days as weekday + day + month", () => {
    expect(dayLabel("2026-10-07", today)).toBe("Wed 7 Oct");
    expect(dayLabel("2025-12-31", today)).toBe("Wed 31 Dec");
  });
  it("crosses a month boundary for yesterday", () => {
    expect(dayLabel("2026-09-30", "2026-10-01")).toBe("Yesterday");
  });
});

describe("A310 — dayDividers", () => {
  const today = "2026-10-10";
  it("puts a divider above the first message of each local day", () => {
    const msgs = [
      { created_at: at(2026, 10, 7, 9) },
      { created_at: at(2026, 10, 7, 9, 1) },
      { created_at: at(2026, 10, 9, 18) },
      { created_at: at(2026, 10, 10, 8) },
      { created_at: at(2026, 10, 10, 8, 2) },
    ];
    expect(dayDividers(msgs, today)).toEqual(["Wed 7 Oct", null, "Yesterday", "Today", null]);
  });
  it("treats unsaved messages (no created_at) as today", () => {
    const msgs = [{ created_at: at(2026, 10, 10, 8) }, {}, {}];
    expect(dayDividers(msgs, today)).toEqual(["Today", null, null]);
    expect(dayDividers([{ created_at: at(2026, 10, 9, 8) }, {}], today)).toEqual([
      "Yesterday",
      "Today",
    ]);
  });
  it("is empty for an empty conversation", () => {
    expect(dayDividers([], today)).toEqual([]);
  });
});

describe("A310 — stale ad-hoc cards", () => {
  const today = "2026-10-10";
  it("a card resolved for today is live", () => {
    expect(isStaleAdhocCard("2026-10-10", at(2026, 10, 10, 9), today)).toBe(false);
  });
  it("a card resolved for another day is stale, whatever its timestamp", () => {
    expect(isStaleAdhocCard("2026-10-07", at(2026, 10, 7, 9), today)).toBe(true);
    // resolved_for_date wins over created_at
    expect(isStaleAdhocCard("2026-10-09", at(2026, 10, 10, 0, 5), today)).toBe(true);
  });
  it("falls back to the message's local day when resolved_for_date is missing", () => {
    expect(isStaleAdhocCard(undefined, at(2026, 10, 8, 9), today)).toBe(true);
    expect(isStaleAdhocCard(undefined, at(2026, 10, 10, 9), today)).toBe(false);
    expect(adhocCardDate(undefined, at(2026, 10, 8, 9))).toBe("2026-10-08");
  });
  it("a card composed in this session (no date at all) is live", () => {
    expect(isStaleAdhocCard(undefined, undefined, today)).toBe(false);
    expect(adhocCardDate(undefined, undefined)).toBeNull();
  });
});

describe("A310 — requestBefore", () => {
  const msgs = [
    { role: "user", content: "first" },
    { role: "assistant", content: "reply" },
    { role: "user", content: "  build me a session  " },
    { role: "assistant", content: "" },
  ];
  it("finds the nearest earlier user turn", () => {
    expect(requestBefore(msgs, 3)).toBe("build me a session");
    expect(requestBefore(msgs, 1)).toBe("first");
  });
  it("is null when the request is not loaded (paginated away)", () => {
    expect(requestBefore(msgs, 0)).toBeNull();
    expect(requestBefore([{ role: "assistant", content: "x" }], 0)).toBeNull();
  });
});

describe("A310 — failed send recovery", () => {
  it("drops the unsaved trailing user bubble of the failed text", () => {
    const msgs = [
      { id: "1", role: "assistant", content: "hi" },
      { role: "user", content: "help" },
    ];
    expect(dropFailedUserTurn(msgs, "help")).toEqual([msgs[0]]);
  });
  it("never drops a saved turn, another text, or an assistant turn", () => {
    const saved = [{ id: "9", role: "user", content: "help" }];
    expect(dropFailedUserTurn(saved, "help")).toBe(saved);
    const other = [{ role: "user", content: "other" }];
    expect(dropFailedUserTurn(other, "help")).toBe(other);
    const assistant = [{ role: "assistant", content: "help" }];
    expect(dropFailedUserTurn(assistant, "help")).toBe(assistant);
    expect(dropFailedUserTurn([], "help")).toEqual([]);
  });
  it("offers Retry except for the daily limit and the subscription gate", () => {
    expect(isRetryableStatus(undefined)).toBe(true); // network drop
    expect(isRetryableStatus(500)).toBe(true);
    expect(isRetryableStatus(502)).toBe(true);
    expect(isRetryableStatus(429)).toBe(false);
    expect(isRetryableStatus(402)).toBe(false);
  });
});
