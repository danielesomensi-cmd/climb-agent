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

const CACHE_KEY = "weather_v2"; // v2: English strings — invalidates stale Italian cache
const CACHE_TTL_MS = 15 * 60 * 1000; // mirrors the server-side 15-min window

interface CachedWeather {
  weather: Weather;
  ts: number;
}

/** Band → accent classes + label. */
const BAND_META: Record<ConditionBand, { label: string; ring: string; dot: string; text: string }> = {
  prime: { label: "Prime conditions", ring: "border-emerald-700/40 from-emerald-900/30 to-emerald-800/10", dot: "bg-emerald-400", text: "text-emerald-400" },
  ok: { label: "OK conditions", ring: "border-amber-700/40 from-amber-900/30 to-amber-800/10", dot: "bg-amber-400", text: "text-amber-400" },
  poor: { label: "Poor conditions", ring: "border-zinc-700/50 from-zinc-800/40 to-zinc-800/10", dot: "bg-zinc-400", text: "text-zinc-400" },
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

/**
 * Short climbing-context phrase for the verdict. Explains *why* the band is
 * what it is, in friction terms — including the "hot but windy" nuance Daniele
 * asked for (the band itself stays unchanged; only the copy reflects the help).
 */
function contextPhrase(w: Weather): string {
  if (w.condition_code < 800) return "Wet: rock is off";
  if (w.condition_band === "prime") return "Great friction — a day for projects";
  if (w.condition_band === "ok") return "Decent conditions";
  // poor — identify the limiting factor
  if (w.dew_point > 14) return "Humid: greasy holds, poor friction";
  if (w.temp > 24) return w.wind >= 12 ? "Hot, but the wind helps a bit" : "Hot: sweaty skin, low friction";
  if (w.temp < -6) return "Too cold: numb fingers";
  return "Poor conditions";
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
  const [open, setOpen] = useState(false);

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
      className={`rounded-xl bg-gradient-to-r ${meta.ring} border`}
    >
      {/* Collapsed header — tap to expand details (progressive disclosure) */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-3 p-4 text-left"
      >
        <span className="text-2xl shrink-0" aria-hidden="true">
          {weatherEmoji(weather.condition_code)}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2">
            <span className="text-lg font-semibold text-zinc-100">{Math.round(weather.temp)}°C</span>
            <span className="text-sm text-zinc-400">{weather.condition_text}</span>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full ${meta.dot}`} aria-hidden="true" />
          <span className={`text-xs font-medium ${meta.text}`}>{meta.label}</span>
          <svg
            className={`h-4 w-4 text-zinc-500 transition-transform ${open ? "rotate-180" : ""}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {/* Expanded detail */}
      {open && (
        <div className="border-t border-white/5 px-4 pb-4 pt-3">
          <p className={`text-sm font-medium ${meta.text}`}>{contextPhrase(weather)}</p>
          <dl className="mt-2 grid grid-cols-3 gap-2 text-center">
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-zinc-500">Humidity</dt>
              <dd className="text-sm text-zinc-200">{weather.humidity}%</dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-zinc-500">Dew point</dt>
              <dd className="text-sm text-zinc-200">{Math.round(weather.dew_point)}°C</dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-zinc-500">Wind</dt>
              <dd className="text-sm text-zinc-200">{Math.round(weather.wind)} km/h</dd>
              <dd className="text-[11px] capitalize text-zinc-500">{weather.wind_label}</dd>
            </div>
          </dl>
        </div>
      )}
    </section>
  );
}
