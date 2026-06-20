"use client";

import { useEffect, useState } from "react";
import { getWeather } from "@/lib/api";
import type { OutdoorConditions, CatalogConditionBand, Weather } from "@/lib/types";

/**
 * A226 / A227 — outdoor conditions widget. Compact band pill (temp + band) that
 * expands to a detail panel: feels-like, wind speed + direction, humidity, dew
 * point, cloud cover and precipitation probability. All fields are optional —
 * each renders only when present. Renders NOTHING when conditions are absent
 * (no weather → no widget — graceful).
 *
 * B265 — the widget is now self-sufficient. It prefers the strategy-derived
 * `conditions` (a day-specific forecast with the 4-value catalog band) but, when
 * those are absent — e.g. a restored in-progress session where `strategy` is
 * null, or an out-of-window forecast date — it falls back to a direct live
 * `/api/weather` fetch using `coords`. This decouples the widget from the
 * strategy resolve (which had caused it to "regress twice" and show stale
 * errors) so live weather loads whenever geolocation is available. Failures stay
 * graceful: no data → no widget, never a red error box.
 */

const BAND_META: Record<CatalogConditionBand, { label: string; ring: string; dot: string; text: string }> = {
  prime: { label: "Prime", ring: "border-emerald-700/40 bg-emerald-900/20", dot: "bg-emerald-400", text: "text-emerald-400" },
  ok: { label: "OK", ring: "border-amber-700/40 bg-amber-900/20", dot: "bg-amber-400", text: "text-amber-400" },
  poor_hot_humid: { label: "Hot / humid", ring: "border-orange-800/40 bg-orange-900/20", dot: "bg-orange-400", text: "text-orange-400" },
  poor_cold_dry: { label: "Cold / dry", ring: "border-sky-800/40 bg-sky-900/20", dot: "bg-sky-400", text: "text-sky-400" },
};

const COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];

/** Wind degrees → 8-point compass label. */
function windDir(deg: number): string {
  return COMPASS[Math.round(deg / 45) % 8];
}

// Cold floor mirrors backend weather_v1.TEMP_OK_MIN_C — below it a "poor" band is
// cold/dry, otherwise hot/humid. Keeps the client live-fetch fallback consistent
// with the server-side catalog_condition_band mapping.
const TEMP_OK_MIN_C = -6.0;

/** Replicate backend `catalog_condition_band`: 3-value weather band → 4-value. */
function catalogBand(temp: number, band: Weather["condition_band"]): CatalogConditionBand {
  if (band !== "poor") return band; // prime | ok pass through
  return temp < TEMP_OK_MIN_C ? "poor_cold_dry" : "poor_hot_humid";
}

/** Map a live `/api/weather` response → the widget's conditions shape. */
function weatherToConditions(w: Weather): OutdoorConditions {
  return {
    temperature: w.temp,
    feels_like: w.feels_like ?? undefined,
    humidity: w.humidity,
    dew_point: w.dew_point,
    wind: w.wind,
    wind_label: w.wind_label,
    wind_deg: w.wind_deg ?? undefined,
    cloud_cover: w.cloud_cover ?? undefined,
    precip_prob: w.precip_prob ?? undefined,
    condition_band: catalogBand(w.temp, w.condition_band),
  };
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="text-sm text-zinc-200">{value}</dd>
    </div>
  );
}

export function ConditionBadge({
  conditions,
  coords,
}: {
  conditions?: OutdoorConditions | null;
  coords?: { lat: number; lon: number } | null;
}) {
  const [open, setOpen] = useState(false);
  const [fetched, setFetched] = useState<OutdoorConditions | null>(null);

  const hasStrategyConditions = !!conditions && conditions.condition_band != null;

  // Fallback: when strategy didn't supply conditions but we have coordinates,
  // pull current live weather directly. Fully graceful — any failure (no key,
  // 503, denied) leaves the widget hidden rather than erroring.
  useEffect(() => {
    if (hasStrategyConditions || !coords) return;
    let cancelled = false;
    getWeather(coords.lat, coords.lon)
      .then((w) => { if (!cancelled) setFetched(weatherToConditions(w)); })
      .catch(() => { /* provider unreachable — stay hidden */ });
    return () => { cancelled = true; };
  }, [hasStrategyConditions, coords]);

  const c = hasStrategyConditions ? conditions! : fetched;
  if (!c || c.condition_band == null) return null;
  const meta = BAND_META[c.condition_band];
  if (!meta) return null;
  // Only offer expansion if there's at least one extra detail to show.
  const hasDetail =
    c.feels_like != null ||
    c.dew_point != null ||
    c.wind != null ||
    c.cloud_cover != null ||
    c.precip_prob != null ||
    c.humidity != null;

  return (
    <div className={`rounded-xl border ${meta.ring}`}>
      <button
        type="button"
        onClick={() => hasDetail && setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
      >
        <span className={`h-2 w-2 shrink-0 rounded-full ${meta.dot}`} aria-hidden="true" />
        <span className={`text-sm font-medium ${meta.text}`}>{meta.label}</span>
        {c.temperature != null && (
          <span className="text-sm text-zinc-200">{Math.round(c.temperature)}°C</span>
        )}
        {c.feels_like != null && Math.round(c.feels_like) !== Math.round(c.temperature ?? c.feels_like) && (
          <span className="text-xs text-zinc-500">feels {Math.round(c.feels_like)}°</span>
        )}
        {hasDetail && (
          <svg
            className={`ml-auto h-4 w-4 shrink-0 text-zinc-500 transition-transform ${open ? "rotate-180" : ""}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        )}
      </button>

      {open && hasDetail && (
        <dl className="grid grid-cols-3 gap-3 border-t border-white/5 px-3 pb-3 pt-2">
          {c.feels_like != null && <Detail label="Feels like" value={`${Math.round(c.feels_like)}°C`} />}
          {c.humidity != null && <Detail label="Humidity" value={`${Math.round(c.humidity)}%`} />}
          {c.dew_point != null && <Detail label="Dew point" value={`${Math.round(c.dew_point)}°C`} />}
          {c.wind != null && (
            <Detail
              label="Wind"
              value={`${Math.round(c.wind)} km/h${c.wind_deg != null ? ` ${windDir(c.wind_deg)}` : ""}`}
            />
          )}
          {c.cloud_cover != null && <Detail label="Cloud" value={`${Math.round(c.cloud_cover)}%`} />}
          {c.precip_prob != null && <Detail label="Precip" value={`${Math.round(c.precip_prob)}%`} />}
        </dl>
      )}
    </div>
  );
}
