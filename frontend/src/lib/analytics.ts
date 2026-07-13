import { track } from "@vercel/analytics";

const STORAGE_KEY = "climb_agent_utm";
const EXPIRY_MS = 30 * 24 * 60 * 60 * 1000;

const UTM_KEYS = [
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_content",
  "utm_term",
] as const;

type UtmKey = (typeof UTM_KEYS)[number];
type UtmParams = Partial<Record<UtmKey, string>>;

interface StoredUtm {
  params: UtmParams;
  // A233: first-touch attribution beyond UTM. Optional so records written
  // before A233 (params-only) keep parsing.
  referrer?: string;
  landing_page?: string;
  first_touch_at?: string;
  expires_at: number;
}

function readStored(): StoredUtm | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredUtm;
    if (!parsed.expires_at || Date.now() > parsed.expires_at) {
      window.localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function readFromUrl(): UtmParams {
  if (typeof window === "undefined") return {};
  const search = new URLSearchParams(window.location.search);
  const params: UtmParams = {};
  for (const key of UTM_KEYS) {
    const value = search.get(key);
    if (value) params[key] = value;
  }
  return params;
}

/**
 * First-touch attribution: on the first visit (no unexpired record), store
 * UTM params, external referrer, landing page, and timestamp with a 30-day
 * expiry. A233: unlike the pre-A233 behavior, the record is written even
 * without UTM params — referrer + landing page alone distinguish Reddit
 * from QR/direct traffic. Safe to call on every page mount; subsequent
 * calls are no-ops until expiry (true first-touch).
 */
export function captureUtmOnMount(): void {
  if (typeof window === "undefined") return;
  if (readStored()) return;
  const ref = document.referrer || "";
  const external = ref && !ref.startsWith(window.location.origin) ? ref : "";
  const record: StoredUtm = {
    params: readFromUrl(),
    referrer: external.slice(0, 200),
    landing_page: window.location.pathname.slice(0, 200),
    first_touch_at: new Date().toISOString(),
    expires_at: Date.now() + EXPIRY_MS,
  };
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(record));
  } catch {
    // quota exceeded or disabled — silently skip
  }
}

export function getPersistedUtm(): UtmParams {
  return readStored()?.params ?? {};
}

/** A233: flat attribution record for the onboarding payload — only truthy
 * values, so an empty capture yields {} and the backend stores nothing. */
export function getAttribution(): Record<string, string> {
  const stored = readStored();
  if (!stored) return {};
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(stored.params)) {
    if (v) out[k] = v;
  }
  if (stored.referrer) out.referrer = stored.referrer;
  if (stored.landing_page) out.landing_page = stored.landing_page;
  if (stored.first_touch_at) out.first_touch_at = stored.first_touch_at;
  return out;
}

type EventProps = Record<string, string | number | boolean | null>;

/**
 * Fire a Vercel Analytics custom event with persisted UTM params auto-attached.
 * Props passed in win over persisted UTM on key collision.
 */
export function trackEvent(name: string, props?: EventProps): void {
  const utm = getPersistedUtm();
  const merged: EventProps = { ...utm, ...(props ?? {}) };
  track(name, merged);
}
