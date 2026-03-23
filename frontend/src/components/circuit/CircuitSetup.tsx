"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Flame } from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────

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
  { key: "duration", label: "Duration", default: 10, min: 5, max: 20, step: 1, unit: "min" },
  { key: "work", label: "Work", default: 50, min: 20, max: 60, step: 5, unit: "s" },
  { key: "rest", label: "Rest", default: 10, min: 5, max: 30, step: 5, unit: "s" },
];

type ParamValues = Record<string, number>;

function getDefaults(): ParamValues {
  const v: ParamValues = {};
  for (const p of PARAMS) v[p.key] = p.default;
  return v;
}

// ── ParamRow ───────────────────────────────────────────────────────────

function ParamRow({
  config,
  value,
  onChange,
}: {
  config: ParamConfig;
  value: number;
  onChange: (v: number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const speedRef = useRef(0);

  const clamp = useCallback(
    (v: number) => Math.max(config.min, Math.min(config.max, v)),
    [config.min, config.max]
  );

  const startHold = useCallback(
    (direction: 1 | -1) => {
      speedRef.current = 0;
      timeoutRef.current = setTimeout(() => {
        intervalRef.current = setInterval(() => {
          speedRef.current++;
          const step =
            speedRef.current > 20
              ? config.step * 5
              : speedRef.current > 10
              ? config.step * 2
              : config.step;
          onChange(clamp(value + direction * step));
        }, 80);
      }, 400);
    },
    [value, onChange, clamp, config.step]
  );

  const stopHold = useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    if (intervalRef.current) clearInterval(intervalRef.current);
    timeoutRef.current = null;
    intervalRef.current = null;
  }, []);

  useEffect(() => () => stopHold(), [stopHold]);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  const handleStartEdit = () => {
    setEditValue(String(value));
    setEditing(true);
  };

  const commitEdit = () => {
    const parsed = parseInt(editValue, 10);
    if (!isNaN(parsed)) onChange(clamp(parsed));
    setEditing(false);
  };

  const displayValue = config.unit === "min" ? `${value} min` : `${value}s`;

  return (
    <div className="flex items-center gap-3 py-2.5">
      <span className="min-w-[72px] text-sm font-medium text-foreground">
        {config.label}
      </span>
      <div className="ml-auto flex items-center gap-1">
        <button
          onClick={() => onChange(clamp(value - config.step))}
          onPointerDown={() => startHold(-1)}
          onPointerUp={stopHold}
          onPointerLeave={stopHold}
          onPointerCancel={stopHold}
          disabled={value <= config.min}
          className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted text-foreground transition-colors active:bg-muted/70 disabled:opacity-30"
          aria-label={`Decrease ${config.label}`}
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round">
            <path d="M5 12h14" />
          </svg>
        </button>

        {editing ? (
          <input
            ref={inputRef}
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value.replace(/[^0-9]/g, ""))}
            onBlur={commitEdit}
            onKeyDown={(e) => { if (e.key === "Enter") commitEdit(); }}
            className="h-10 w-16 rounded-lg bg-primary/10 text-center text-base font-bold text-primary outline-none ring-2 ring-primary/30"
          />
        ) : (
          <button
            onClick={handleStartEdit}
            className="flex h-10 min-w-[64px] items-center justify-center rounded-lg bg-card px-2 text-base font-bold tabular-nums text-foreground transition-colors hover:bg-primary/10 hover:text-primary"
          >
            {displayValue}
          </button>
        )}

        <button
          onClick={() => onChange(clamp(value + config.step))}
          onPointerDown={() => startHold(1)}
          onPointerUp={stopHold}
          onPointerLeave={stopHold}
          onPointerCancel={stopHold}
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

// ── CircuitSetup ───────────────────────────────────────────────────────

export interface CircuitConfig {
  durationMin: number;
  workSeconds: number;
  restSeconds: number;
  totalExercises: number;
}

interface CircuitSetupProps {
  onStart: (config: CircuitConfig) => void;
  onCancel: () => void;
}

export function CircuitSetup({ onStart, onCancel }: CircuitSetupProps) {
  const [values, setValues] = useState<ParamValues>(getDefaults);

  const update = useCallback((key: string, val: number) => {
    setValues((prev) => ({ ...prev, [key]: val }));
  }, []);

  const { duration, work, rest } = values;
  const totalSeconds = duration * 60;
  const cycleSeconds = work + rest;
  const totalExercises = Math.floor(totalSeconds / cycleSeconds);
  const actualSeconds = totalExercises * cycleSeconds;
  const actualMin = Math.floor(actualSeconds / 60);
  const actualSec = actualSeconds % 60;

  return (
    <div className="flex flex-col gap-5 px-4">
      {/* Header */}
      <div className="flex flex-col items-center gap-2 pt-4">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-500/20">
          <Flame className="size-8 text-emerald-400" />
        </div>
        <h2 className="text-xl font-bold">Core Circuit</h2>
        <p className="text-sm text-muted-foreground text-center">
          Guided bodyweight core workout with timer
        </p>
      </div>

      {/* Parameters */}
      <div className="rounded-2xl border border-border bg-card/50 px-3">
        {PARAMS.map((p, i) => (
          <div key={p.key}>
            {i > 0 && <div className="border-t border-border/50" />}
            <ParamRow
              config={p}
              value={values[p.key]}
              onChange={(v) => update(p.key, v)}
            />
          </div>
        ))}
      </div>

      {/* Computed summary */}
      <div className="text-center">
        <span className="text-lg font-bold tabular-nums">{totalExercises} exercises</span>
        <span className="text-muted-foreground"> · </span>
        <span className="text-lg font-bold tabular-nums">
          {actualMin}:{String(actualSec).padStart(2, "0")}
        </span>
      </div>

      {/* Start */}
      <button
        onClick={() => onStart({ durationMin: duration, workSeconds: work, restSeconds: rest, totalExercises })}
        disabled={totalExercises < 1}
        className="flex h-14 w-full items-center justify-center gap-3 rounded-2xl bg-emerald-600 text-lg font-bold text-white shadow-lg shadow-emerald-600/25 transition-all active:scale-[0.98] disabled:opacity-50"
      >
        <svg className="h-6 w-6" viewBox="0 0 24 24" fill="currentColor">
          <path d="M8 5v14l11-7z" />
        </svg>
        START CIRCUIT
      </button>

      {/* Cancel */}
      <button
        onClick={onCancel}
        className="text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        Cancel
      </button>
    </div>
  );
}
