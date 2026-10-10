"use client";

import { useSyncExternalStore } from "react";

/**
 * A308 — true while `query` matches. False on the server and wherever
 * `matchMedia` is missing (jsdom tests), so the desktop layout is the default.
 */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      if (typeof window === "undefined" || !window.matchMedia) return () => {};
      const mql = window.matchMedia(query);
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    },
    () => (typeof window !== "undefined" && !!window.matchMedia ? window.matchMedia(query).matches : false),
    () => false,
  );
}
