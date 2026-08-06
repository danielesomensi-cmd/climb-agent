"use client";

import { useState, useRef, useEffect, useLayoutEffect } from "react";
import { Info } from "lucide-react";
import type { AssessmentProfile } from "@/lib/types";
import { getRadarLabels, type Discipline } from "@/lib/gradeUtils";
import {
  buildAxisTooltipCopy,
  buildEliteAxisTooltipCopy,
  computeTooltipShift,
  shouldFlipAbove,
} from "@/lib/radarTooltip";
import {
  computeEliteScores,
  hasAnyEliteScore,
  type EliteRawInputs,
} from "@/lib/eliteScoring";
import {
  LABEL_LINE_HEIGHT,
  radarOuterWidth,
  radarViewBox,
  splitAxisLabel,
} from "@/lib/radarLabels";

const AXIS_KEYS: (keyof AssessmentProfile)[] = [
  "finger_strength",
  "pulling_strength",
  "power_endurance",
  "technique",
  "endurance",
];

/** Which scale the axes are read against. Component state only — never stored. */
type RadarMode = "goal" | "elite";

interface RadarChartProps {
  profile: AssessmentProfile;
  size?: number;
  discipline?: Discipline;
  /** Active goal grade — drives the target-relative tooltip framing (B304). */
  targetGrade?: string | null;
  /**
   * A267 — raw measurements for the display-only Elite comparison mode. Pass
   * them to show the `[ Goal | Elite ]` toggle; omit and the radar behaves
   * exactly as before. Nothing computed from these is persisted or sent
   * anywhere: see the header of `lib/eliteScoring.ts`.
   */
  eliteInputs?: EliteRawInputs | null;
}

/** Read env(safe-area-inset-*) as pixels via a hidden probe element. */
function readSafeAreaInsets(): { left: number; right: number; bottom: number } {
  if (typeof document === "undefined") return { left: 0, right: 0, bottom: 0 };
  const probe = document.createElement("div");
  probe.style.cssText =
    "position:fixed;left:0;top:0;visibility:hidden;pointer-events:none;" +
    "padding-left:env(safe-area-inset-left);" +
    "padding-right:env(safe-area-inset-right);" +
    "padding-bottom:env(safe-area-inset-bottom)";
  document.body.appendChild(probe);
  const cs = getComputedStyle(probe);
  const insets = {
    left: parseFloat(cs.paddingLeft) || 0,
    right: parseFloat(cs.paddingRight) || 0,
    bottom: parseFloat(cs.paddingBottom) || 0,
  };
  probe.remove();
  return insets;
}

function AxisTooltip({
  axis,
  discipline,
  targetGrade,
  mode,
  onClose,
}: {
  axis: string;
  discipline: Discipline;
  targetGrade?: string | null;
  mode: RadarMode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  // Measure once after layout, then position by mutating the node directly.
  // Direct DOM writes (not setState) avoid a re-render pass and are the
  // idiomatic "measure then place" pattern for a one-shot popover. The box
  // starts hidden so it is never painted in its unclamped position (D260 A).
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || typeof window === "undefined") return;
    const insets = readSafeAreaInsets();
    const rect = el.getBoundingClientRect();
    const dx = computeTooltipShift({
      left: rect.left,
      right: rect.right,
      viewportWidth: window.innerWidth,
      insetLeft: insets.left,
      insetRight: insets.right,
    });
    // Flip above when a downward-opening popover would fall under the fixed
    // 3.5rem tab bar (see (main)/layout.tsx) + safe area.
    if (
      shouldFlipAbove({
        bottom: rect.bottom,
        viewportHeight: window.innerHeight,
        bottomSafe: 64 + insets.bottom,
      })
    ) {
      el.style.top = "auto";
      el.style.bottom = "100%";
      el.style.marginTop = "0px";
      el.style.marginBottom = "6px";
    }
    el.style.transform = `translateX(calc(-50% + ${dx}px))`;
    el.style.visibility = "visible";
  }, [axis, targetGrade, mode]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [onClose]);

  const copy =
    mode === "elite"
      ? buildEliteAxisTooltipCopy(axis, discipline)
      : buildAxisTooltipCopy(axis, discipline, targetGrade);
  if (!copy) return null;

  return (
    <div
      ref={ref}
      role="tooltip"
      className="absolute z-50 w-72 max-w-[calc(100vw-24px)] rounded-lg border border-border bg-background p-3 shadow-lg text-sm"
      style={{
        left: "50%",
        top: "100%",
        marginTop: 6,
        transform: "translateX(-50%)",
        visibility: "hidden",
      }}
    >
      <p className="font-semibold mb-1">{copy.label}</p>
      <p className="text-muted-foreground text-xs leading-relaxed mb-2">{copy.description}</p>
      <p className="text-xs text-muted-foreground mb-2">{copy.relative}</p>
      <p className="text-xs text-muted-foreground/80 italic">{copy.low}</p>
    </div>
  );
}

export function RadarChart({
  profile,
  size = 280,
  discipline,
  targetGrade,
  eliteInputs,
}: RadarChartProps) {
  const labels = getRadarLabels(discipline);
  const AXES = AXIS_KEYS.map((key) => ({ key, label: labels[key] ?? key }));
  const [openTooltip, setOpenTooltip] = useState<string | null>(null);
  // A267 — mode is component state and nothing else. No DB field, no
  // localStorage, no query param: a comparison lens is not a user setting.
  const [mode, setMode] = useState<RadarMode>("goal");

  const eliteScores = eliteInputs ? computeEliteScores(eliteInputs) : null;
  const showToggle = !!eliteScores && hasAnyEliteScore(eliteScores);
  const activeMode: RadarMode = showToggle ? mode : "goal";

  /** Value plotted per axis. `null` in Elite mode = greyed, not zero. */
  function axisValue(key: (typeof AXIS_KEYS)[number]): number | null {
    if (activeMode === "elite") return eliteScores?.[key] ?? null;
    return profile[key];
  }

  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 40;
  const n = AXES.length;

  const angleStep = (2 * Math.PI) / n;
  const offset = -Math.PI / 2; // start from top

  function point(i: number, value: number): [number, number] {
    const angle = offset + i * angleStep;
    const dist = (value / 100) * r;
    return [cx + dist * Math.cos(angle), cy + dist * Math.sin(angle)];
  }

  // Grid lines (20, 40, 60, 80, 100)
  const gridLevels = [20, 40, 60, 80, 100];

  // Data points — only the axes that have a value on the active scale. In Goal
  // mode that is always all five; in Elite mode the axes without an anchor are
  // simply absent, because plotting them at 0 would read as "you score zero"
  // rather than "we have no benchmark".
  const livePoints = AXES.map((axis, i) => {
    const v = axisValue(axis.key);
    return v === null ? null : { i, xy: point(i, v) };
  }).filter((p): p is { i: number; xy: [number, number] } => p !== null);
  // A polygon needs three vertices. With fewer, spokes from the centre carry
  // the same information without pretending to be a shape.
  const polygon =
    livePoints.length >= 3
      ? livePoints.map(({ xy: [x, y] }) => `${x},${y}`).join(" ")
      : null;

  return (
    <div className="flex flex-col items-center gap-4">
      {showToggle && (
        <div className="flex flex-col items-center gap-1.5">
          <div
            role="group"
            aria-label="Comparison scale"
            className="inline-flex rounded-full border border-border p-0.5 text-xs"
          >
            {(["goal", "elite"] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                aria-pressed={activeMode === m}
                className={
                  "min-h-[32px] rounded-full px-4 font-medium transition-colors " +
                  (activeMode === m
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground")
                }
              >
                {m === "goal" ? "Goal" : "Elite"}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            {activeMode === "elite"
              ? "vs elite level"
              : targetGrade
                ? `Readiness for ${targetGrade}`
                : "Readiness for your goal grade"}
          </p>
        </div>
      )}
      {/* B318 — the SVG is now responsive and its box is wider than the
          drawing. Before, `width={size}` with `viewBox="0 0 size size"` clipped
          the right-hand axis label ("Pulling Strenç") because the text extended
          past the coordinate box, and on a viewport narrower than `size` the
          whole chart overflowed its container instead of scaling. */}
      <svg
        width="100%"
        viewBox={radarViewBox(size)}
        style={{ maxWidth: radarOuterWidth(size) }}
        preserveAspectRatio="xMidYMid meet"
        className="h-auto"
      >
        {/* Grid circles */}
        {gridLevels.map((level) => {
          const gridPoints = Array.from({ length: n }, (_, i) => point(i, level));
          const gridPolygon = gridPoints.map(([x, y]) => `${x},${y}`).join(" ");
          return (
            <polygon
              key={level}
              points={gridPolygon}
              fill="none"
              stroke="currentColor"
              strokeOpacity={0.15}
              strokeWidth={1}
            />
          );
        })}

        {/* Axis lines */}
        {AXES.map((_, i) => {
          const [x, y] = point(i, 100);
          return (
            <line
              key={i}
              x1={cx}
              y1={cy}
              x2={x}
              y2={y}
              stroke="currentColor"
              strokeOpacity={0.15}
              strokeWidth={1}
            />
          );
        })}

        {/* Data polygon */}
        {polygon && (
          <polygon points={polygon} fill="var(--primary)" fillOpacity={0.25} stroke="var(--primary)" strokeWidth={2} />
        )}

        {/* Spokes — only when there are too few axes to form a polygon (A267) */}
        {!polygon &&
          livePoints.map(({ i, xy: [x, y] }) => (
            <line
              key={`spoke-${i}`}
              x1={cx}
              y1={cy}
              x2={x}
              y2={y}
              stroke="var(--primary)"
              strokeWidth={2}
            />
          ))}

        {/* Data points */}
        {livePoints.map(({ i, xy: [x, y] }) => (
          <circle key={i} cx={x} cy={y} r={4} fill="var(--primary)" />
        ))}

        {/* Labels — B318: two-word labels wrap onto two balanced lines, which
            roughly halves their width. Together with the padded viewBox this
            keeps every axis name fully visible; abbreviating or truncating was
            not an option, the axis vocabulary is closed (docs/vocabulary_v1.md). */}
        {AXES.map((axis, i) => {
          const [x, y] = point(i, 120);
          const lines = splitAxisLabel(axis.label);
          // Centre the block vertically on the anchor: one line stays put, two
          // lines straddle it, so the label reads as attached to its axis.
          const startDy = lines.length === 1 ? 0 : -(LABEL_LINE_HEIGHT / 2);
          return (
            <text
              key={axis.key}
              x={x}
              y={y}
              textAnchor="middle"
              dominantBaseline="middle"
              className="fill-foreground text-[10px]"
            >
              {lines.map((line, li) => (
                <tspan
                  key={line}
                  x={x}
                  dy={li === 0 ? startDy : LABEL_LINE_HEIGHT}
                >
                  {line}
                </tspan>
              ))}
            </text>
          );
        })}
      </svg>

      {/* Legend below with (i) tooltips */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm">
        {AXES.map((axis) => {
          const value = axisValue(axis.key);
          return (
            <div key={axis.key} className="relative flex items-center justify-between gap-2">
              <span
                className={
                  "flex items-center gap-1 " +
                  (value === null ? "text-muted-foreground/50" : "text-muted-foreground")
                }
              >
                {axis.label}
                <button
                  type="button"
                  onClick={() => setOpenTooltip(openTooltip === axis.key ? null : axis.key)}
                  className="inline-flex text-muted-foreground/50 hover:text-muted-foreground transition-colors"
                  aria-label={`Info about ${axis.label}`}
                >
                  <Info size={14} />
                </button>
              </span>
              {value === null ? (
                <span className="font-mono text-muted-foreground/50" aria-label="No elite benchmark">
                  —
                </span>
              ) : activeMode === "goal" && value >= 100 ? (
                <span className="inline-flex items-center rounded-full bg-primary/15 px-2 py-0.5 text-xs font-medium text-primary">
                  ✓ At target
                </span>
              ) : (
                <span className="font-mono font-semibold">{value}</span>
              )}
              {openTooltip === axis.key && (
                <AxisTooltip
                  axis={axis.key}
                  discipline={discipline ?? "lead"}
                  targetGrade={targetGrade}
                  mode={activeMode}
                  onClose={() => setOpenTooltip(null)}
                />
              )}
            </div>
          );
        })}
      </div>

      {activeMode === "elite" && livePoints.length < AXES.length && (
        <p className="max-w-xs text-center text-xs text-muted-foreground/70">
          Greyed axes have no defensible elite benchmark yet — they are shown for
          your goal only.
        </p>
      )}
    </div>
  );
}
