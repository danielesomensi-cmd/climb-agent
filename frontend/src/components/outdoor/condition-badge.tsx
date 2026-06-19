"use client";

import type { OutdoorConditions, CatalogConditionBand } from "@/lib/types";

/**
 * A226 — outdoor conditions badge. Shows temp + humidity + condition_band
 * (4-value catalog vocabulary). Renders NOTHING when conditions are absent
 * (no weather → no badge — graceful).
 */

const BAND_META: Record<CatalogConditionBand, { label: string; ring: string; dot: string; text: string }> = {
  prime: { label: "Prime", ring: "border-emerald-700/40 bg-emerald-900/20", dot: "bg-emerald-400", text: "text-emerald-400" },
  ok: { label: "OK", ring: "border-amber-700/40 bg-amber-900/20", dot: "bg-amber-400", text: "text-amber-400" },
  poor_hot_humid: { label: "Hot / humid", ring: "border-orange-800/40 bg-orange-900/20", dot: "bg-orange-400", text: "text-orange-400" },
  poor_cold_dry: { label: "Cold / dry", ring: "border-sky-800/40 bg-sky-900/20", dot: "bg-sky-400", text: "text-sky-400" },
};

export function ConditionBadge({ conditions }: { conditions?: OutdoorConditions | null }) {
  if (!conditions || conditions.condition_band == null) return null;
  const meta = BAND_META[conditions.condition_band];
  if (!meta) return null;

  return (
    <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs ${meta.ring}`}>
      <span className={`h-2 w-2 rounded-full ${meta.dot}`} aria-hidden="true" />
      <span className={`font-medium ${meta.text}`}>{meta.label}</span>
      {conditions.temperature != null && (
        <span className="text-zinc-300">{Math.round(conditions.temperature)}°C</span>
      )}
      {conditions.humidity != null && (
        <span className="text-zinc-500">{Math.round(conditions.humidity)}% RH</span>
      )}
      {conditions.wind != null && (
        <span className="text-zinc-500">{Math.round(conditions.wind)} km/h</span>
      )}
    </div>
  );
}
