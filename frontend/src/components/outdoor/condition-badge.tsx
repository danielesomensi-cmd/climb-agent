"use client";

import { useState } from "react";
import type { OutdoorConditions, CatalogConditionBand } from "@/lib/types";

/**
 * A226 / A227 — outdoor conditions widget. Compact band pill (temp + band) that
 * expands to a detail panel: feels-like, wind speed + direction, humidity, dew
 * point, cloud cover and precipitation probability. All fields are optional —
 * each renders only when present. Renders NOTHING when conditions are absent
 * (no weather → no widget — graceful).
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

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="text-sm text-zinc-200">{value}</dd>
    </div>
  );
}

export function ConditionBadge({ conditions }: { conditions?: OutdoorConditions | null }) {
  const [open, setOpen] = useState(false);
  if (!conditions || conditions.condition_band == null) return null;
  const meta = BAND_META[conditions.condition_band];
  if (!meta) return null;

  const c = conditions;
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
