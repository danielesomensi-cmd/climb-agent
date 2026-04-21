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
 * First-touch attribution: if UTM params are present in the URL AND no
 * unexpired record already exists, store them with a 30-day expiry.
 * Safe to call on every page mount; subsequent calls are no-ops until expiry.
 */
export function captureUtmOnMount(): void {
  if (typeof window === "undefined") return;
  if (readStored()) return;
  const fromUrl = readFromUrl();
  if (Object.keys(fromUrl).length === 0) return;
  const record: StoredUtm = {
    params: fromUrl,
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
