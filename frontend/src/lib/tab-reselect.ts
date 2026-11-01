"use client";

import { useEffect, useRef } from "react";

/**
 * A323 — tapping the bottom-nav tab of the page you are already on.
 *
 * A Link to the current URL does nothing visible, so on /week the only way
 * back to the top (or back to today) was scrolling by hand. BottomNav now
 * swallows that tap for the tabs listed here and fires TAB_RESELECT_EVENT;
 * the page decides what the tap means.
 */
export const TAB_RESELECT_EVENT = "climb:tab-reselect";

/** Tabs whose page handles a re-tap. Any other tab keeps the plain Link. */
export const TAB_RESELECT_HREFS: ReadonlySet<string> = new Set(["/week"]);

/** Within this many px of the top the page counts as "at the top" (as A308). */
export const AT_TOP_PX = 8;

export function emitTabReselect(href: string): void {
  window.dispatchEvent(new CustomEvent<string>(TAB_RESELECT_EVENT, { detail: href }));
}

/** Calls `handler` when the tab `href` is tapped while its page is open. */
export function useTabReselect(href: string, handler: () => void): void {
  const handlerRef = useRef(handler);
  useEffect(() => {
    handlerRef.current = handler;
  });
  useEffect(() => {
    const listener = (e: Event) => {
      if ((e as CustomEvent<string>).detail === href) handlerRef.current();
    };
    window.addEventListener(TAB_RESELECT_EVENT, listener);
    return () => window.removeEventListener(TAB_RESELECT_EVENT, listener);
  }, [href]);
}

export type WeekReselectAction = "top" | "today" | "current_week" | "none";

/**
 * A323 — what a re-tap on Week does. It alternates by position, so it never
 * depends on what the previous tap did:
 * - scrolled anywhere → back to the top;
 * - at the top of the current week → today's card;
 * - at the top of another week → back to the current week (which lands on today);
 * - at the top of the current week without today in it → nothing to do.
 */
export function weekReselectAction(args: {
  scrollY: number;
  isCurrentWeekView: boolean;
  todayInWeek: boolean;
}): WeekReselectAction {
  if (args.scrollY > AT_TOP_PX) return "top";
  if (!args.isCurrentWeekView) return "current_week";
  return args.todayInWeek ? "today" : "none";
}

/** "smooth", unless the user asked the OS for reduced motion. */
export function scrollBehavior(): ScrollBehavior {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return "smooth";
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
}
