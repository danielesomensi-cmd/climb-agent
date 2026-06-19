"use client";

import { useState } from "react";
import type { OutdoorStrategyResponse, OutdoorModifier } from "@/lib/types";

/**
 * A226 — renders the deterministic resolved strategy + nutrition.
 *
 * - Base fields are rendered plainly.
 * - `modifiers[]` are rendered as separate chips WITH provenance (the dimension
 *   value as a badge) — never fused into the base copy.
 * - `safety:{}` standing reminders (D72 / CUE-02 / D64) are surfaced.
 */

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="mt-0.5 text-sm text-zinc-200">{value}</dd>
    </div>
  );
}

function ListField({ label, items }: { label: string; items: string[] }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="mt-1">
        <ul className="space-y-1">
          {items.map((it, i) => (
            <li key={i} className="flex gap-2 text-sm text-zinc-200">
              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-zinc-500" aria-hidden="true" />
              <span>{it}</span>
            </li>
          ))}
        </ul>
      </dd>
    </div>
  );
}

function ModifierChip({ m }: { m: OutdoorModifier }) {
  return (
    <li className="rounded-lg border border-white/5 bg-zinc-900/40 p-2.5">
      <div className="mb-1 flex flex-wrap items-center gap-1.5">
        <span className="rounded-full bg-indigo-900/40 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-indigo-300">
          {m.value.replace(/_/g, " ")}
        </span>
        <span className="text-[10px] uppercase tracking-wide text-zinc-600">{m.key.replace(/_/g, " ")}</span>
      </div>
      <p className="text-sm text-zinc-300">{m.text}</p>
    </li>
  );
}

export function StrategyView({ data }: { data: OutdoorStrategyResponse }) {
  const { strategy, nutrition, safety } = data;
  const base = strategy.base;
  const [nutOpen, setNutOpen] = useState(false);

  return (
    <div className="space-y-5">
      {/* Strategy base */}
      <dl className="space-y-3">
        <Field label="Warm-up" value={base.warmup_protocol} />
        <Field label="Target burns" value={base.target_burns} />
        <Field label="Rest between attempts" value={base.rest_between_attempts_min} />
        <ListField label="Stop criteria" items={base.stop_criteria} />
        <ListField label="Skin" items={base.skin_tips} />
        <Field label="Time of day" value={base.time_of_day_advice} />
        <Field label="Hours" value={base.hours_plan} />
        <Field label="Downgrade rule" value={base.downgrade_rule} />
      </dl>

      {/* Modifiers (layered, with provenance) */}
      {strategy.modifiers.length > 0 && (
        <div>
          <h4 className="mb-2 text-[11px] uppercase tracking-wide text-zinc-500">
            Adjustments for your day
          </h4>
          <ul className="space-y-2">
            {strategy.modifiers.map((m, i) => (
              <ModifierChip key={i} m={m} />
            ))}
          </ul>
        </div>
      )}

      {/* Nutrition (collapsible) */}
      <div className="rounded-lg border border-white/5">
        <button
          type="button"
          onClick={() => setNutOpen((v) => !v)}
          aria-expanded={nutOpen}
          className="flex w-full items-center justify-between p-3 text-left"
        >
          <span className="text-sm font-medium text-zinc-200">Fueling &amp; hydration</span>
          <svg className={`h-4 w-4 text-zinc-500 transition-transform ${nutOpen ? "rotate-180" : ""}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        {nutOpen && (
          <dl className="space-y-3 border-t border-white/5 p-3">
            {nutrition.day_type_nuance && <Field label="For this day" value={nutrition.day_type_nuance} />}
            <Field label="Before" value={nutrition.pre_day} />
            <Field label="During (long)" value={nutrition.during_by_duration.long} />
            <Field label="Hydration" value={nutrition.hydration_by_climate} />
            <Field label="Caffeine" value={nutrition.caffeine_timing} />
            <Field label="After" value={nutrition.post_day} />
          </dl>
        )}
      </div>

      {/* Safety standing reminders (D72 / CUE-02 / D64) */}
      {Object.keys(safety).length > 0 && (
        <ul className="space-y-1 rounded-lg border border-amber-900/30 bg-amber-950/10 p-3">
          {Object.values(safety).map((s, i) => (
            <li key={i} className="flex gap-2 text-xs text-amber-200/80">
              <span aria-hidden="true">⚠️</span>
              <span>{s}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
