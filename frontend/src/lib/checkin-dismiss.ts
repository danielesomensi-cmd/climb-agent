/**
 * B396 — "Plan your week" dismissal, kept across PWA restarts.
 *
 * It lived in sessionStorage, which iOS clears whenever it closes the PWA: the
 * card came back on every reopen. It is now one localStorage value — the
 * Monday it was dismissed for — so it expires by itself when the target week
 * changes and nothing accumulates.
 */
const KEY = "checkin_dismissed_monday";
const EVENT = "climb-agent:checkin-dismissed";

/** The Monday the card was dismissed for, "" when none (or storage blocked). */
export function readCheckinDismissed(): string {
  try {
    return window.localStorage.getItem(KEY) ?? "";
  } catch {
    return "";
  }
}

export function writeCheckinDismissed(monday: string): void {
  try {
    window.localStorage.setItem(KEY, monday);
  } catch {
    /* private mode / blocked storage: the dismiss lasts until the next render */
  }
  try {
    window.dispatchEvent(new Event(EVENT));
  } catch {
    /* no Event constructor: subscribers just re-read on the next storage event */
  }
}

/**
 * B396 review — forget the dismissal. It is one value for the whole device
 * (the sessionStorage it replaced died with the PWA), so SessionScopeGuard
 * calls this on sign-out and on an account switch: the next user must not
 * inherit the previous one's "Plan your week" dismissal (A245 B-2).
 */
export function clearCheckinDismissed(): void {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* private mode / blocked storage: nothing was kept */
  }
  try {
    window.dispatchEvent(new Event(EVENT));
  } catch {
    /* no Event constructor: subscribers just re-read on the next storage event */
  }
}

/** useSyncExternalStore subscription: this tab's writes and other tabs'. */
export function subscribeCheckinDismissed(onChange: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const onStorage = (e: StorageEvent) => {
    if (e.key === null || e.key === KEY) onChange();
  };
  window.addEventListener(EVENT, onChange);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onStorage);
  };
}
