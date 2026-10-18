/**
 * @vitest-environment jsdom
 *
 * B396 review — the "Plan your week" dismissal moved from sessionStorage to a
 * device-wide localStorage value (lib/checkin-dismiss). SessionScopeGuard
 * purges every device-local trace of the previous user on sign-out and on an
 * account switch (A245 B-2), but did not know about this one: the next user
 * inherited the previous one's dismissal.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const { auth } = vi.hoisted(() => ({
  auth: { current: { isLoaded: true, userId: "user_a" as string | null } },
}));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => auth.current }));

import { SessionScopeGuard } from "@/components/session-scope-guard";
import { clearCheckinDismissed, readCheckinDismissed, writeCheckinDismissed } from "@/lib/checkin-dismiss";

class MemoryStorage {
  private map = new Map<string, string>();
  get length() { return this.map.size; }
  key(i: number) { return Array.from(this.map.keys())[i] ?? null; }
  getItem(k: string) { return this.map.get(k) ?? null; }
  setItem(k: string, v: string) { this.map.set(k, String(v)); }
  removeItem(k: string) { this.map.delete(k); }
  clear() { this.map.clear(); }
}

const qc = new QueryClient();
const guard = () => (
  <QueryClientProvider client={qc}>
    <SessionScopeGuard />
  </QueryClientProvider>
);

beforeEach(() => {
  Object.defineProperty(window, "localStorage", { value: new MemoryStorage(), configurable: true });
  auth.current = { isLoaded: true, userId: "user_a" };
});

afterEach(() => cleanup());

describe("clearCheckinDismissed", () => {
  it("forgets the dismissal and tells the card to re-read", () => {
    writeCheckinDismissed("2026-10-19");
    const onChange = vi.fn();
    window.addEventListener("climb-agent:checkin-dismissed", onChange);
    clearCheckinDismissed();
    window.removeEventListener("climb-agent:checkin-dismissed", onChange);
    expect(readCheckinDismissed()).toBe("");
    expect(onChange).toHaveBeenCalledTimes(1);
  });
});

describe("SessionScopeGuard — the check-in dismissal belongs to the user", () => {
  it("survives a restart of the same user (first observation purges nothing)", () => {
    writeCheckinDismissed("2026-10-19");
    render(guard());
    expect(readCheckinDismissed()).toBe("2026-10-19");
  });

  it("is cleared on an account switch", () => {
    const view = render(guard());
    writeCheckinDismissed("2026-10-19");
    auth.current = { isLoaded: true, userId: "user_b" };
    view.rerender(guard());
    expect(readCheckinDismissed()).toBe("");
  });

  it("is cleared on sign-out", () => {
    const view = render(guard());
    writeCheckinDismissed("2026-10-19");
    auth.current = { isLoaded: true, userId: null };
    view.rerender(guard());
    expect(readCheckinDismissed()).toBe("");
  });
});
