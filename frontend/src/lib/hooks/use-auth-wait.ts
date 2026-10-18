"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

/**
 * B396 — how long an online page waits for Clerk before treating it as
 * unreachable.
 *
 * Clerk.js comes from the network (B292b): offline it never initialises, and on
 * a dead-but-"online" falesia connection it never finishes either. While it is
 * loading on a working connection (a reload, a deep link) the page must say
 * "loading", not "you're offline" — and not send a request without a token,
 * which can only 401. Past this limit we stop waiting and fall back to the
 * offline / fail-closed answers the app gave before.
 */
export const AUTH_WAIT_MS = 6000;

/**
 * Pure rule: should we stop waiting for Clerk?
 *
 * Never once Clerk has loaded. Immediately when the browser says it is offline
 * (waiting would only delay an answer we already know). Otherwise after
 * `limitMs` without Clerk.
 */
export function shouldStopWaitingForAuth(args: {
  authLoaded: boolean;
  online: boolean;
  waitedMs: number;
  limitMs?: number;
}): boolean {
  if (args.authLoaded) return false;
  if (!args.online) return true;
  return args.waitedMs >= (args.limitMs ?? AUTH_WAIT_MS);
}

function readOnline(): boolean {
  return typeof navigator === "undefined" || navigator.onLine !== false;
}

function subscribeOnline(onChange: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener("online", onChange);
  window.addEventListener("offline", onChange);
  return () => {
    window.removeEventListener("online", onChange);
    window.removeEventListener("offline", onChange);
  };
}

/** B396 — `navigator.onLine` as React state (server render: assume online). */
export function useOnline(): boolean {
  return useSyncExternalStore(subscribeOnline, readOnline, () => true);
}

/**
 * B396 — true once we should stop waiting for Clerk: the browser is offline,
 * or Clerk has not loaded within `limitMs` of this component mounting.
 * Always false once Clerk has loaded.
 */
export function useAuthWaitExpired(authLoaded: boolean, limitMs: number = AUTH_WAIT_MS): boolean {
  const online = useOnline();
  const [timedOut, setTimedOut] = useState(false);

  useEffect(() => {
    if (authLoaded) return;
    const t = window.setTimeout(() => setTimedOut(true), limitMs);
    return () => window.clearTimeout(t);
  }, [authLoaded, limitMs]);

  return shouldStopWaitingForAuth({
    authLoaded,
    online,
    waitedMs: timedOut ? limitMs : 0,
    limitMs,
  });
}
