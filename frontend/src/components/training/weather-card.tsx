"use client";

import { useCallback, useEffect, useState } from "react";
import { MapPin } from "lucide-react";
import { getWeather } from "@/lib/api";
import type { Weather } from "@/lib/types";
import { ConditionsPanel, type ConditionsData } from "@/components/shared/conditions-panel";

/**
 * A224 / A238 — live weather card on /today (Goal A).
 *
 * On mount: request browser geolocation → call the server-side /api/weather
 * proxy → render via the shared ConditionsPanel (A238: same band/headline/
 * qualifiers as the outdoor day widget). Renders NOTHING when geolocation is
 * denied or unavailable, or when the provider is unreachable (graceful
 * fallback — never an intrusive error). Weather is cached briefly in
 * sessionStorage to avoid a refetch / re-prompt on every navigation back
 * to /today.
 */

const CACHE_KEY = "weather_v3"; // v3: A238 shape (friction score, headline, qualifiers)
const CACHE_TTL_MS = 15 * 60 * 1000; // mirrors the server-side 15-min window

interface CachedWeather {
  weather: Weather;
  ts: number;
}

function readCache(): Weather | null {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CachedWeather;
    if (Date.now() - parsed.ts > CACHE_TTL_MS) return null;
    return parsed.weather;
  } catch {
    return null;
  }
}

/** Map the /api/weather payload → the shared panel shape. */
export function weatherToPanel(w: Weather): ConditionsData {
  return {
    band: w.band ?? w.condition_band,
    score: w.friction_score,
    headline: w.headline,
    temp: w.temp,
    feels_like: w.feels_like ?? undefined,
    humidity: w.humidity,
    dew_point: w.dew_point,
    dew_spread: w.dew_spread,
    wind: w.wind,
    wind_deg: w.wind_deg ?? undefined,
    wind_label: w.wind_label,
    cloud_cover: w.cloud_cover ?? undefined,
    precip_prob: w.precip_prob ?? undefined,
    condition_text: w.condition_text,
    condition_code: w.condition_code,
    qualifiers: w.qualifiers,
    best_window: w.best_window ?? null,
  };
}

export function WeatherCard() {
  // Lazy init from sessionStorage. The card only mounts client-side (after the
  // page's `loading` flag clears), so it's never in the hydration pass — reading
  // sessionStorage here causes no mismatch.
  const [weather, setWeather] = useState<Weather | null>(() =>
    typeof window === "undefined" ? null : readCache(),
  );
  // B293 — the iOS geolocation permission popup must never fire on mount
  // without a user gesture (it used to stack with the first-login toasts and
  // modals). "cta" renders a tap-to-load affordance; auto-fetch happens only
  // when the Permissions API says the permission is ALREADY granted (no popup).
  const [mode, setMode] = useState<"idle" | "cta" | "loading" | "hidden">("idle");

  const fetchViaGeolocation = useCallback((onUnavailable: () => void) => {
    let cancelled = false;
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const w = await getWeather(pos.coords.latitude, pos.coords.longitude);
          if (cancelled) return;
          setWeather(w);
          try {
            sessionStorage.setItem(CACHE_KEY, JSON.stringify({ weather: w, ts: Date.now() }));
          } catch {
            /* sessionStorage full / unavailable — non-fatal */
          }
        } catch {
          /* provider unreachable / 503 */
          if (!cancelled) onUnavailable();
        }
      },
      () => {
        /* permission denied or position unavailable */
        if (!cancelled) onUnavailable();
      },
      { timeout: 8000, maximumAge: 15 * 60 * 1000 },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    // Fresh cache already seeded the state → nothing to fetch or ask.
    if (readCache()) return;

    // No geolocation support → silently skip (card stays hidden).
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setMode("hidden");
      return;
    }

    let cancelFetch: (() => void) | undefined;
    let disposed = false;

    if (typeof navigator.permissions?.query === "function") {
      navigator.permissions
        .query({ name: "geolocation" })
        .then((status) => {
          if (disposed) return;
          if (status.state === "granted") {
            // Already granted — no popup possible, safe to fetch on mount.
            setMode("loading");
            cancelFetch = fetchViaGeolocation(() => setMode("hidden"));
          } else if (status.state === "denied") {
            setMode("hidden");
          } else {
            setMode("cta");
          }
        })
        .catch(() => {
          if (!disposed) setMode("cta");
        });
    } else {
      // Permissions API unavailable — we cannot know without prompting, so
      // wait for the gesture.
      setMode("cta");
    }

    return () => {
      disposed = true;
      cancelFetch?.();
    };
  }, [fetchViaGeolocation]);

  const handleShowConditions = () => {
    setMode("loading");
    fetchViaGeolocation(() => setMode("hidden"));
  };

  if (weather) {
    return <ConditionsPanel data={weatherToPanel(weather)} ariaLabel="Current weather conditions" />;
  }

  if (mode === "cta" || mode === "loading") {
    return (
      <button
        type="button"
        disabled={mode === "loading"}
        onClick={handleShowConditions}
        className="flex w-full items-center gap-2 rounded-lg border border-dashed px-3 py-2.5 text-left text-sm text-muted-foreground hover:bg-accent transition-colors disabled:opacity-60"
      >
        <MapPin className="size-4 shrink-0" />
        {mode === "loading" ? "Checking conditions..." : "Show outdoor conditions (uses your location)"}
      </button>
    );
  }

  return null;
}
