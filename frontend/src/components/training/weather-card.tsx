"use client";

import { useEffect, useState } from "react";
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

  useEffect(() => {
    let cancelled = false;

    // Fresh cache already seeded the state → nothing to fetch.
    if (readCache()) return;

    // No geolocation support → silently skip (card stays hidden).
    if (typeof navigator === "undefined" || !navigator.geolocation) return;

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
          /* provider unreachable / 503 — keep the card hidden */
        }
      },
      () => {
        /* permission denied or position unavailable — keep the card hidden */
      },
      { timeout: 8000, maximumAge: 15 * 60 * 1000 },
    );

    return () => {
      cancelled = true;
    };
  }, []);

  if (!weather) return null;

  return <ConditionsPanel data={weatherToPanel(weather)} ariaLabel="Current weather conditions" />;
}
