/**
 * @vitest-environment jsdom
 *
 * A323 — a tap on the Week tab while already on /week: to the top, then to
 * today's card, and so on. BottomNav swallows the re-tap and fires
 * TAB_RESELECT_EVENT; the week page decides with weekReselectAction.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import {
  AT_TOP_PX,
  TAB_RESELECT_EVENT,
  useTabReselect,
  weekReselectAction,
} from "@/lib/tab-reselect";

const nav = vi.hoisted(() => ({ pathname: "/week" }));

vi.mock("next/navigation", () => ({ usePathname: () => nav.pathname }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));
vi.mock("next/dynamic", () => ({ default: () => () => null }));

afterEach(() => {
  cleanup();
  nav.pathname = "/week";
});

describe("weekReselectAction", () => {
  it("scrolled anywhere → back to the top", () => {
    expect(weekReselectAction({ scrollY: 1200, isCurrentWeekView: true, todayInWeek: true })).toBe("top");
    expect(weekReselectAction({ scrollY: AT_TOP_PX + 1, isCurrentWeekView: false, todayInWeek: false })).toBe("top");
  });

  it("at the top of the current week → today's card", () => {
    expect(weekReselectAction({ scrollY: 0, isCurrentWeekView: true, todayInWeek: true })).toBe("today");
    expect(weekReselectAction({ scrollY: AT_TOP_PX, isCurrentWeekView: true, todayInWeek: true })).toBe("today");
  });

  it("at the top of another week → back to the current week", () => {
    expect(weekReselectAction({ scrollY: 0, isCurrentWeekView: false, todayInWeek: false })).toBe("current_week");
  });

  it("at the top of the current week without today in it → nothing", () => {
    expect(weekReselectAction({ scrollY: 0, isCurrentWeekView: true, todayInWeek: false })).toBe("none");
  });

  it("alternates: top → today → top", () => {
    const view = { isCurrentWeekView: true, todayInWeek: true };
    // Today's card sits ~600 px down: after the first tap we are there.
    expect(weekReselectAction({ scrollY: 600, ...view })).toBe("top");
    expect(weekReselectAction({ scrollY: 0, ...view })).toBe("today");
    expect(weekReselectAction({ scrollY: 600, ...view })).toBe("top");
  });
});

async function renderNav() {
  const { BottomNav } = await import("@/components/layout/bottom-nav");
  render(<BottomNav />);
}

function listen() {
  const seen: string[] = [];
  const listener = (e: Event) => seen.push((e as CustomEvent<string>).detail);
  window.addEventListener(TAB_RESELECT_EVENT, listener);
  return { seen, stop: () => window.removeEventListener(TAB_RESELECT_EVENT, listener) };
}

describe("BottomNav re-tap", () => {
  it("Week tapped on /week: no navigation, the page is told", async () => {
    await renderNav();
    const { seen, stop } = listen();
    const link = screen.getByRole("link", { name: "Week" });
    const notCancelled = fireEvent.click(link);
    stop();
    expect(notCancelled).toBe(false); // preventDefault: the Link does not navigate
    expect(seen).toEqual(["/week"]);
  });

  it("Week tapped from another page: a plain navigation", async () => {
    nav.pathname = "/today";
    await renderNav();
    const { seen, stop } = listen();
    const notCancelled = fireEvent.click(screen.getByRole("link", { name: "Week" }));
    stop();
    expect(notCancelled).toBe(true);
    expect(seen).toEqual([]);
  });

  it("only tabs whose page handles it: Today re-tapped on /today stays a Link", async () => {
    nav.pathname = "/today";
    await renderNav();
    const { seen, stop } = listen();
    const notCancelled = fireEvent.click(screen.getByRole("link", { name: "Today" }));
    stop();
    expect(notCancelled).toBe(true);
    expect(seen).toEqual([]);
  });

  it("cmd/ctrl-click keeps the Link", async () => {
    await renderNav();
    const { seen, stop } = listen();
    const link = screen.getByRole("link", { name: "Week" });
    expect(fireEvent.click(link, { metaKey: true })).toBe(true);
    expect(fireEvent.click(link, { ctrlKey: true })).toBe(true);
    stop();
    expect(seen).toEqual([]);
  });
});

describe("useTabReselect", () => {
  it("calls the latest handler, only for its own tab, and unsubscribes on unmount", () => {
    const first = vi.fn();
    const second = vi.fn();
    const { rerender, unmount } = renderHook(({ h }) => useTabReselect("/week", h), {
      initialProps: { h: first },
    });
    rerender({ h: second });
    window.dispatchEvent(new CustomEvent(TAB_RESELECT_EVENT, { detail: "/today" }));
    window.dispatchEvent(new CustomEvent(TAB_RESELECT_EVENT, { detail: "/week" }));
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
    unmount();
    window.dispatchEvent(new CustomEvent(TAB_RESELECT_EVENT, { detail: "/week" }));
    expect(second).toHaveBeenCalledTimes(1);
  });
});
