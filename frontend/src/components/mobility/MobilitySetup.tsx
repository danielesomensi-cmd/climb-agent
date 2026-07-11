"use client";

// A231 — Mobility flow setup, mirroring the Core Circuit setup UX:
// pick regions (multi-select), total time, pace and rest — the system
// picks the stretches and shows a live "N stretches · M:SS" counter.

import { useCallback, useEffect, useRef, useState } from "react";
import { StretchHorizontal } from "lucide-react";
import { getMobilityFlow, type MobilityFlowPlan, type MobilityRegion } from "@/lib/api";
import { RegionFigure } from "./RegionFigure";

// ── Param stepper (same interaction as CircuitSetup) ───────────────────

interface ParamConfig {
  key: string;
  label: string;
  default: number;
  min: number;
  max: number;
  step: number;
  unit: "min" | "s";
}

const PARAMS: ParamConfig[] = [
  { key: "duration", label: "Duration", default: 15, min: 5, max: 45, step: 5, unit: "min" },
  { key: "rest", label: "Rest", default: 10, min: 5, max: 30, step: 5, unit: "s" },
];

type ParamValues = Record<string, number>;

function getDefaults(): ParamValues {
  const v: ParamValues = {};
  for (const p of PARAMS) v[p.key] = p.default;
  return v;
}

function ParamRow({
  config,
  value,
  onChange,
}: {
  config: ParamConfig;
  value: number;
  onChange: (v: number) => void;
}) {
  const clamp = useCallback(
    (v: number) => Math.max(config.min, Math.min(config.max, v)),
    [config.min, config.max]
  );
  const displayValue = config.unit === "min" ? `${value} min` : `${value}s`;

  return (
    <div className="flex items-center gap-3 py-2.5">
      <span className="min-w-[72px] text-sm font-medium text-foreground">{config.label}</span>
      <div className="ml-auto flex items-center gap-1">
        <button
          onClick={() => onChange(clamp(value - config.step))}
          disabled={value <= config.min}
          className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted text-foreground transition-colors active:bg-muted/70 disabled:opacity-30"
          aria-label={`Decrease ${config.label}`}
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round">
            <path d="M5 12h14" />
          </svg>
        </button>
        <span className="flex h-10 min-w-[64px] items-center justify-center rounded-lg bg-card px-2 text-base font-bold tabular-nums text-foreground">
          {displayValue}
        </span>
        <button
          onClick={() => onChange(clamp(value + config.step))}
          disabled={value >= config.max}
          className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted text-foreground transition-colors active:bg-muted/70 disabled:opacity-30"
          aria-label={`Increase ${config.label}`}
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round">
            <path d="M12 5v14M5 12h14" />
          </svg>
        </button>
      </div>
    </div>
  );
}

// ── MobilitySetup ──────────────────────────────────────────────────────

export interface MobilityConfig {
  regions: string[];
  minutes: number;
  pace: string;
  restSeconds: number;
  plan: MobilityFlowPlan;
}

interface MobilitySetupProps {
  regions: MobilityRegion[]; // from /api/mobility/pool — labels + counts
  today: string;
  onStart: (config: MobilityConfig) => void;
  onCancel: () => void;
}

const PACES = [
  { id: "quick", label: "Quick" },
  { id: "standard", label: "Standard" },
  { id: "deep", label: "Deep" },
] as const;

const LS_REGIONS_KEY = "mobility_regions";
const LS_PACE_KEY = "mobility_pace";

export function MobilitySetup({ regions, today, onStart, onCancel }: MobilitySetupProps) {
  const [values, setValues] = useState<ParamValues>(getDefaults);
  const [pace, setPace] = useState<string>(() => {
    if (typeof window === "undefined") return "standard";
    const stored = localStorage.getItem(LS_PACE_KEY);
    return stored && PACES.some((p) => p.id === stored) ? stored : "standard";
  });
  const [selected, setSelected] = useState<Set<string>>(() => {
    if (typeof window === "undefined") return new Set();
    try {
      const stored = JSON.parse(localStorage.getItem(LS_REGIONS_KEY) || "[]") as string[];
      return new Set(stored);
    } catch {
      return new Set();
    }
  });

  const [plan, setPlan] = useState<MobilityFlowPlan | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    localStorage.setItem(LS_PACE_KEY, pace);
  }, [pace]);
  useEffect(() => {
    localStorage.setItem(LS_REGIONS_KEY, JSON.stringify(Array.from(selected)));
  }, [selected]);

  const { duration, rest } = values;

  // Live plan preview (debounced)
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      if (selected.size === 0) {
        setPlan(null);
        return;
      }
      setPlanLoading(true);
      getMobilityFlow({
        regions: Array.from(selected),
        minutes: duration,
        pace,
        rest,
        date: today,
      })
        .then((p) => {
          setPlan(p);
          setError(null);
        })
        .catch((e) => setError(e instanceof Error ? e.message : "Failed to build flow"))
        .finally(() => setPlanLoading(false));
    }, 250);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [selected, duration, pace, rest, today]);

  const toggleRegion = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleStart = async () => {
    if (selected.size === 0) return;
    setStarting(true);
    setError(null);
    try {
      // Fresh plan at start time (the debounced one may be stale)
      const freshPlan = await getMobilityFlow({
        regions: Array.from(selected),
        minutes: duration,
        pace,
        rest,
        date: today,
      });
      onStart({
        regions: Array.from(selected),
        minutes: duration,
        pace,
        restSeconds: rest,
        plan: freshPlan,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start");
      setStarting(false);
    }
  };

  const totalMin = plan ? Math.floor(plan.total_seconds / 60) : 0;
  const totalSec = plan ? plan.total_seconds % 60 : 0;

  return (
    <div className="flex flex-col gap-5 px-4">
      {/* Header */}
      <div className="flex flex-col items-center gap-2 pt-4">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-violet-500/20">
          <StretchHorizontal className="size-8 text-violet-400" />
        </div>
        <h2 className="text-xl font-bold">Stretching & Mobility</h2>
        <p className="text-center text-sm text-muted-foreground">
          Pick regions and time — we build the guided flow
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Region multi-select */}
      <div className="grid grid-cols-3 gap-2">
        {regions.map((r) => {
          const isSelected = selected.has(r.id);
          return (
            <button
              key={r.id}
              onClick={() => toggleRegion(r.id)}
              className={`relative flex flex-col items-center gap-1 rounded-xl border p-2 pt-3 transition-all active:scale-[0.97] ${
                isSelected
                  ? "border-violet-500 bg-violet-500/10"
                  : "border-border bg-card hover:border-violet-500/40"
              }`}
            >
              {isSelected && (
                <div className="absolute right-1.5 top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-violet-500 text-[9px] text-white">
                  ✓
                </div>
              )}
              <div className="h-14">
                <RegionFigure region={r.id} />
              </div>
              <div className="text-center text-[11px] font-medium leading-tight">{r.label}</div>
            </button>
          );
        })}
      </div>

      {/* Duration + Rest steppers */}
      <div className="rounded-2xl border border-border bg-card/50 px-3">
        {PARAMS.map((p, i) => (
          <div key={p.key}>
            {i > 0 && <div className="border-t border-border/50" />}
            <ParamRow
              config={p}
              value={values[p.key]}
              onChange={(v) => setValues((prev) => ({ ...prev, [p.key]: v }))}
            />
          </div>
        ))}
      </div>

      {/* Pace toggle */}
      <div className="flex items-center justify-between rounded-2xl border border-border bg-card/50 px-3 py-3">
        <span className="text-sm font-medium text-foreground">Pace</span>
        <div className="flex rounded-lg border border-border bg-muted/50 p-0.5">
          {PACES.map((p) => (
            <button
              key={p.id}
              onClick={() => setPace(p.id)}
              className={`rounded-md px-3.5 py-1.5 text-sm font-semibold transition-all ${
                pace === p.id
                  ? "bg-violet-600 text-white shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* GATE-2 note */}
      {plan && plan.excluded_pre_performance.length > 0 && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-400">
          ⚠️ Climbing later today — {plan.excluded_pre_performance.join(", ")} skipped
          (forearm-flexor stretches can reduce grip strength for up to 1h).
        </div>
      )}

      {/* Computed summary */}
      <div className="text-center">
        {selected.size === 0 ? (
          <span className="text-sm text-muted-foreground">Select at least one region</span>
        ) : planLoading && !plan ? (
          <span className="text-sm text-muted-foreground">Building flow…</span>
        ) : plan ? (
          <>
            <span className="text-lg font-bold tabular-nums">{plan.entry_count} stretches</span>
            <span className="text-muted-foreground"> · </span>
            <span className="text-lg font-bold tabular-nums">
              {totalMin}:{String(totalSec).padStart(2, "0")}
            </span>
          </>
        ) : null}
      </div>

      {/* Start */}
      <button
        onClick={handleStart}
        disabled={selected.size === 0 || starting || !plan || plan.steps.length === 0}
        className="flex h-14 w-full items-center justify-center gap-3 rounded-2xl bg-violet-600 text-lg font-bold text-white shadow-lg shadow-violet-600/25 transition-all active:scale-[0.98] disabled:opacity-50"
      >
        <svg className="h-6 w-6" viewBox="0 0 24 24" fill="currentColor">
          <path d="M8 5v14l11-7z" />
        </svg>
        {starting ? "STARTING…" : "START STRETCHING"}
      </button>

      {/* Cancel */}
      <button
        onClick={onCancel}
        className="text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        Cancel
      </button>
    </div>
  );
}
