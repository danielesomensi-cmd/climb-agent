"use client";

import { useState } from "react";
import type { BestWindow, ConditionBand, WeatherQualifiers } from "@/lib/types";

/**
 * A238 — unified weather-conditions panel, shared by the /today card and the
 * outdoor day widget. One normalized data shape → identical band, headline,
 * qualifier chips and best-window line on every surface (hard requirement).
 *
 * All fields are optional: legacy payloads (old logs, strategy conditions
 * without the A238 fields) render what they have — missing headline/qualifiers
 * simply don't show. Collapsible: band + headline always visible, metric grid
 * behind a tap.
 */

export interface ConditionsData {
  band: ConditionBand;
  score?: number;
  headline?: string;
  temp?: number;
  feels_like?: number;
  humidity?: number;
  dew_point?: number;
  dew_spread?: number;
  wind?: number;
  wind_deg?: number;
  wind_label?: string;
  cloud_cover?: number;
  precip_prob?: number;
  condition_text?: string;
  condition_code?: number;
  qualifiers?: WeatherQualifiers;
  best_window?: BestWindow | null;
}

/** Band → chip styling. PRIME emerald, GOOD green, OK amber, POOR red. */
const BAND_META: Record<ConditionBand, { label: string; ring: string; chip: string; text: string }> = {
  prime: { label: "PRIME", ring: "border-emerald-700/40 from-emerald-900/30 to-emerald-800/10", chip: "bg-emerald-600 text-white", text: "text-emerald-400" },
  good: { label: "GOOD", ring: "border-green-700/40 from-green-900/30 to-green-800/10", chip: "bg-green-600 text-white", text: "text-green-400" },
  ok: { label: "OK", ring: "border-amber-700/40 from-amber-900/30 to-amber-800/10", chip: "bg-amber-600 text-white", text: "text-amber-400" },
  poor: { label: "POOR", ring: "border-red-800/40 from-red-950/30 to-red-900/10", chip: "bg-red-700 text-white", text: "text-red-400" },
};

const COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
function windDir(deg: number): string {
  return COMPASS[Math.round(deg / 45) % 8];
}

/** Dynamic icon driven by the dominant condition. */
function dominantEmoji(d: ConditionsData): string {
  const wet = (d.condition_code != null && d.condition_code < 700) || (d.precip_prob ?? 0) > 30 || d.qualifiers?.precip === "wet rock risk";
  if (wet) return "🌧";
  if ((d.temp ?? 15) > 24) return "🔥";
  if ((d.dew_spread ?? 99) < 5 || (d.humidity ?? 0) > 60) return "💧";
  if ((d.wind ?? 0) > 25) return "💨";
  if ((d.temp ?? 15) < 12) return "❄️";
  if (d.condition_code === 800) return "☀️";
  if (d.condition_code != null && d.condition_code > 800) return "☁️";
  return "☀️";
}

function Metric({ label, value, sub, chip }: { label: string; value: string; sub?: string; chip?: string }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="text-sm text-zinc-200">{value}</dd>
      {sub && <dd className="text-[11px] text-zinc-500">{sub}</dd>}
      {chip && (
        <dd className="mt-0.5">
          <span className="inline-block rounded-full border border-white/10 bg-white/5 px-1.5 py-px text-[10px] text-zinc-400">{chip}</span>
        </dd>
      )}
    </div>
  );
}

export function ConditionsPanel({ data, ariaLabel }: { data: ConditionsData; ariaLabel: string }) {
  const [open, setOpen] = useState(false);
  const meta = BAND_META[data.band] ?? BAND_META.ok;

  const hasDetail =
    data.feels_like != null || data.humidity != null || data.dew_point != null ||
    data.wind != null || data.cloud_cover != null || data.precip_prob != null;

  return (
    <section aria-label={ariaLabel} className={`rounded-xl border bg-gradient-to-r ${meta.ring}`}>
      {/* Header — band chip is the visual anchor */}
      <button
        type="button"
        onClick={() => hasDetail && setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-3 p-4 text-left"
      >
        <span className="text-2xl shrink-0" aria-hidden="true">{dominantEmoji(data)}</span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className={`rounded-md px-2 py-0.5 text-sm font-bold tracking-wide ${meta.chip}`}>{meta.label}</span>
            {data.temp != null && (
              <span className="text-lg font-semibold text-zinc-100">{Math.round(data.temp)}°C</span>
            )}
            {data.condition_text && <span className="text-sm text-zinc-400">{data.condition_text}</span>}
            {data.score != null && (
              <span className="text-xs text-zinc-500" title="Friction score">{data.score}/100</span>
            )}
          </div>
        </div>
        {hasDetail && (
          <svg
            className={`h-4 w-4 shrink-0 text-zinc-500 transition-transform ${open ? "rotate-180" : ""}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        )}
      </button>

      {/* Headline + best window — always visible */}
      {(data.headline || data.best_window) && (
        <div className="px-4 pb-3 -mt-1.5">
          {data.headline && <p className={`text-sm font-medium ${meta.text}`}>{data.headline}</p>}
          {data.best_window && (
            <p className="mt-0.5 text-xs text-zinc-400">
              Peak conditions from {data.best_window.from} — {data.best_window.reason}.
            </p>
          )}
        </div>
      )}

      {/* Expanded metric grid with qualifier chips */}
      {open && hasDetail && (
        <div className="border-t border-white/5 px-4 pb-3 pt-3">
          <dl className="grid grid-cols-3 gap-3">
            {data.feels_like != null && data.temp != null && Math.round(data.feels_like) !== Math.round(data.temp) && (
              <Metric label="Feels like" value={`${Math.round(data.feels_like)}°C`} />
            )}
            {data.humidity != null && (
              <Metric label="Humidity" value={`${Math.round(data.humidity)}%`} chip={data.qualifiers?.humidity} />
            )}
            {data.dew_point != null && (
              <Metric
                label="Dew spread"
                value={data.dew_spread != null ? `${Math.round(data.dew_spread)}° below air` : `${Math.round(data.dew_point)}°C`}
                sub={data.dew_spread != null ? `dew point ${Math.round(data.dew_point)}°C` : undefined}
                chip={data.qualifiers?.dew_spread}
              />
            )}
            {data.wind != null && (
              <Metric
                label="Wind"
                value={`${Math.round(data.wind)} km/h${data.wind_deg != null ? ` ${windDir(data.wind_deg)}` : ""}`}
                sub={data.wind_label}
                chip={data.qualifiers?.wind}
              />
            )}
            {data.cloud_cover != null && <Metric label="Cloud" value={`${Math.round(data.cloud_cover)}%`} />}
            {data.precip_prob != null && (
              <Metric label="Precip" value={`${Math.round(data.precip_prob)}%`} chip={data.qualifiers?.precip} />
            )}
          </dl>
          <p className="mt-2 text-right text-[10px] text-zinc-600">Weather data by OpenWeather</p>
        </div>
      )}
    </section>
  );
}
