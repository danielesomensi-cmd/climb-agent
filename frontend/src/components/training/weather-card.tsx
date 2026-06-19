"use client";

import { useEffect, useState } from "react";
import { getWeather } from "@/lib/api";
import type { Weather, ConditionBand } from "@/lib/types";

/**
 * A224 — live weather card on /today (Goal A).
 *
 * On mount: request browser geolocation → call the server-side /api/weather
 * proxy → render current temp / humidity / condition with a subtle
 * condition_band color accent. Renders NOTHING when geolocation is denied or
 * unavailable, or when the provider is unreachable (graceful fallback — never
 * an intrusive error). Weather is cached briefly in sessionStorage to avoid a
 * refetch / re-prompt on every navigation back to /today.
 */

const CACHE_KEY = "weather_v1";
const CACHE_TTL_MS = 15 * 60 * 1000; // mirrors the server-side 15-min window

interface CachedWeather {
  weather: Weather;
  ts: number;
}

/** Band → accent classes + Italian label. */
const BAND_META: Record<ConditionBand, { label: string; ring: string; dot: string; text: string }> = {
  prime: { label: "Condizioni ottime", ring: "border-emerald-700/40 from-emerald-900/30 to-emerald-800/10", dot: "bg-emerald-400", text: "text-emerald-400" },
  ok: { label: "Condizioni discrete", ring: "border-amber-700/40 from-amber-900/30 to-amber-800/10", dot: "bg-amber-400", text: "text-amber-400" },
  poor: { label: "Condizioni scarse", ring: "border-zinc-700/50 from-zinc-800/40 to-zinc-800/10", dot: "bg-zinc-400", text: "text-zinc-400" },
};

/** OWM condition id → emoji. */
function weatherEmoji(code: number): string {
  if (code < 300) return "⛈️"; // thunderstorm
  if (code < 600) return "🌧️"; // drizzle / rain
  if (code < 700) return "❄️"; // snow
  if (code < 800) return "🌫️"; // atmosphere (fog / mist)
  if (code === 800) return "☀️"; // clear
  return "☁️"; // clouds
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

  const meta = BAND_META[weather.condition_band];

  return (
    <section
      aria-label="Current weather conditions"
      className={`rounded-xl bg-gradient-to-r ${meta.ring} border p-4`}
    >
      <div className="flex items-center gap-3">
        <span className="text-2xl shrink-0" aria-hidden="true">
          {weatherEmoji(weather.condition_code)}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="text-lg font-semibold text-zinc-100">{Math.round(weather.temp)}°C</span>
            <span className="truncate text-sm text-zinc-400">{weather.condition_text}</span>
          </div>
          <p className="mt-0.5 text-xs text-zinc-500">
            Umidità {weather.humidity}% · Rugiada {Math.round(weather.dew_point)}°C · Vento {Math.round(weather.wind)} km/h
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full ${meta.dot}`} aria-hidden="true" />
          <span className={`text-xs font-medium ${meta.text}`}>{meta.label}</span>
        </div>
      </div>
    </section>
  );
}
