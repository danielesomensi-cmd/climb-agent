"use client";

import { useEffect, useState } from "react";
import { getWeather } from "@/lib/api";
import type { OutdoorConditions, ConditionBand } from "@/lib/types";
import { ConditionsPanel, type ConditionsData } from "@/components/shared/conditions-panel";
import { weatherToPanel } from "@/components/training/weather-card";

/**
 * A226 / A227 / A238 — outdoor conditions widget. Renders through the shared
 * ConditionsPanel so band, headline and qualifier chips are IDENTICAL to the
 * /today weather card (A238 hard requirement). Renders NOTHING when conditions
 * are absent (no weather → no widget — graceful).
 *
 * B265 — the widget is self-sufficient. It prefers the strategy-derived
 * `conditions` (a day-specific forecast) but, when those are absent — e.g. a
 * restored in-progress session where `strategy` is null, or an out-of-window
 * forecast date — it falls back to a direct live `/api/weather` fetch using
 * `coords`. Failures stay graceful: no data → no widget, never an error box.
 */

const NEW_BANDS: ConditionBand[] = ["prime", "good", "ok", "poor"];

/** Band for legacy payloads: prefer the A238 field, then a valid raw weather
 *  band, then the 4-value catalog band collapsed back to the display vocabulary. */
function bandOf(c: OutdoorConditions): ConditionBand | null {
  if (c.band && NEW_BANDS.includes(c.band)) return c.band;
  if (c.weather_band_raw && NEW_BANDS.includes(c.weather_band_raw as ConditionBand)) {
    return c.weather_band_raw as ConditionBand;
  }
  if (c.condition_band === "prime" || c.condition_band === "ok") return c.condition_band;
  if (c.condition_band === "poor_hot_humid" || c.condition_band === "poor_cold_dry") return "poor";
  return null;
}

/** Map strategy/log conditions → the shared panel shape. */
function conditionsToPanel(c: OutdoorConditions): ConditionsData | null {
  const band = bandOf(c);
  if (!band) return null;
  return {
    band,
    score: c.friction_score,
    headline: c.headline,
    temp: c.temperature,
    feels_like: c.feels_like,
    humidity: c.humidity,
    dew_point: c.dew_point,
    dew_spread: c.dew_spread ?? (c.temperature != null && c.dew_point != null ? c.temperature - c.dew_point : undefined),
    wind: c.wind,
    wind_deg: c.wind_deg,
    wind_label: c.wind_label,
    cloud_cover: c.cloud_cover,
    precip_prob: c.precip_prob,
    qualifiers: c.qualifiers,
  };
}

export function ConditionBadge({
  conditions,
  coords,
}: {
  conditions?: OutdoorConditions | null;
  coords?: { lat: number; lon: number } | null;
}) {
  const [fetched, setFetched] = useState<ConditionsData | null>(null);

  const hasStrategyConditions = !!conditions && conditions.condition_band != null;

  // Fallback: when strategy didn't supply conditions but we have coordinates,
  // pull current live weather directly. Fully graceful — any failure (no key,
  // 503, denied) leaves the widget hidden rather than erroring.
  useEffect(() => {
    if (hasStrategyConditions || !coords) return;
    let cancelled = false;
    getWeather(coords.lat, coords.lon)
      .then((w) => { if (!cancelled) setFetched(weatherToPanel(w)); })
      .catch(() => { /* provider unreachable — stay hidden */ });
    return () => { cancelled = true; };
  }, [hasStrategyConditions, coords]);

  const data = hasStrategyConditions ? conditionsToPanel(conditions!) : fetched;
  if (!data) return null;

  return <ConditionsPanel data={data} ariaLabel="Outdoor conditions" />;
}
