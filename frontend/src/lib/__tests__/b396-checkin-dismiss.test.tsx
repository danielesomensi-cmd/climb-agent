/**
 * @vitest-environment jsdom
 *
 * B396 — "Plan your week" dismissal survives the PWA being closed.
 *
 * It was kept in sessionStorage, which iOS clears whenever it closes the PWA:
 * the card came back at every reopen. And it was read in an effect, so the
 * card appeared one frame after the page, pushing Start down. Now it is one
 * localStorage value (the Monday it was dismissed for) read during render.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import { WeeklyCheckinCard } from "@/components/training/weekly-checkin-card";
import { readCheckinDismissed, writeCheckinDismissed } from "@/lib/checkin-dismiss";

class MemoryStorage {
  private map = new Map<string, string>();
  get length() { return this.map.size; }
  key(i: number) { return Array.from(this.map.keys())[i] ?? null; }
  getItem(k: string) { return this.map.get(k) ?? null; }
  setItem(k: string, v: string) { this.map.set(k, String(v)); }
  removeItem(k: string) { this.map.delete(k); }
  clear() { this.map.clear(); }
}

beforeEach(() => {
  // Node's own (flag-gated) Web Storage shadows jsdom's here: give the window
  // real, isolated stores.
  Object.defineProperty(window, "localStorage", { value: new MemoryStorage(), configurable: true });
  Object.defineProperty(window, "sessionStorage", { value: new MemoryStorage(), configurable: true });
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 9, 18, 9, 0)); // Sunday → target Monday 2026-10-19
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("checkin-dismiss store", () => {
  it("round-trips the dismissed Monday", () => {
    expect(readCheckinDismissed()).toBe("");
    writeCheckinDismissed("2026-10-19");
    expect(readCheckinDismissed()).toBe("2026-10-19");
  });
});

describe("WeeklyCheckinCard", () => {
  it("is on screen in the first client render (no late pop-in above Start)", () => {
    render(<WeeklyCheckinCard weekPlan={null} onPlanUpdated={() => {}} />);
    expect(screen.getByText("Plan your week")).toBeTruthy();
  });

  it("stays dismissed across a remount — i.e. a PWA restart", () => {
    const first = render(<WeeklyCheckinCard weekPlan={null} onPlanUpdated={() => {}} />);
    act(() => writeCheckinDismissed("2026-10-19"));
    expect(screen.queryByText("Plan your week")).toBeNull();
    first.unmount();

    window.sessionStorage.clear(); // what iOS does when it closes the PWA
    render(<WeeklyCheckinCard weekPlan={null} onPlanUpdated={() => {}} />);
    expect(screen.queryByText("Plan your week")).toBeNull();
  });

  it("comes back for a new target week", () => {
    window.localStorage.setItem("checkin_dismissed_monday", "2026-10-12");
    render(<WeeklyCheckinCard weekPlan={null} onPlanUpdated={() => {}} />);
    expect(screen.getByText("Plan your week")).toBeTruthy();
  });

  it("is hidden Tuesday to Saturday", () => {
    vi.setSystemTime(new Date(2026, 9, 21, 9, 0)); // Wednesday
    render(<WeeklyCheckinCard weekPlan={null} onPlanUpdated={() => {}} />);
    expect(screen.queryByText("Plan your week")).toBeNull();
  });
});
