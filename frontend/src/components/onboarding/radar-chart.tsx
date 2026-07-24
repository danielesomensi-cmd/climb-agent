"use client";

import { useState, useRef, useEffect, useLayoutEffect } from "react";
import { Info } from "lucide-react";
import type { AssessmentProfile } from "@/lib/types";
import { getRadarLabels, type Discipline } from "@/lib/gradeUtils";
import {
  buildAxisTooltipCopy,
  computeTooltipShift,
  shouldFlipAbove,
} from "@/lib/radarTooltip";

const AXIS_KEYS: (keyof AssessmentProfile)[] = [
  "finger_strength",
  "pulling_strength",
  "power_endurance",
  "technique",
  "endurance",
];

interface RadarChartProps {
  profile: AssessmentProfile;
  size?: number;
  discipline?: Discipline;
  /** Active goal grade — drives the target-relative tooltip framing (B304). */
  targetGrade?: string | null;
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
  onClose,
}: {
  axis: string;
  discipline: Discipline;
  targetGrade?: string | null;
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
  }, [axis, targetGrade]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [onClose]);

  const copy = buildAxisTooltipCopy(axis, discipline, targetGrade);
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

export function RadarChart({ profile, size = 280, discipline, targetGrade }: RadarChartProps) {
  const labels = getRadarLabels(discipline);
  const AXES = AXIS_KEYS.map((key) => ({ key, label: labels[key] ?? key }));
  const [openTooltip, setOpenTooltip] = useState<string | null>(null);

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

  // Data points
  const points = AXES.map((axis, i) => point(i, profile[axis.key]));
  const polygon = points.map(([x, y]) => `${x},${y}`).join(" ");

  return (
    <div className="flex flex-col items-center gap-4">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
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
        <polygon points={polygon} fill="var(--primary)" fillOpacity={0.25} stroke="var(--primary)" strokeWidth={2} />

        {/* Data points */}
        {points.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r={4} fill="var(--primary)" />
        ))}

        {/* Labels */}
        {AXES.map((axis, i) => {
          const [x, y] = point(i, 120);
          return (
            <text
              key={axis.key}
              x={x}
              y={y}
              textAnchor="middle"
              dominantBaseline="middle"
              className="fill-foreground text-[10px]"
            >
              {axis.label}
            </text>
          );
        })}
      </svg>

      {/* Legend below with (i) tooltips */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm">
        {AXES.map((axis) => (
          <div key={axis.key} className="relative flex items-center justify-between gap-2">
            <span className="flex items-center gap-1 text-muted-foreground">
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
            {profile[axis.key] >= 100 ? (
              <span className="inline-flex items-center rounded-full bg-primary/15 px-2 py-0.5 text-xs font-medium text-primary">
                ✓ At target
              </span>
            ) : (
              <span className="font-mono font-semibold">{profile[axis.key]}</span>
            )}
            {openTooltip === axis.key && (
              <AxisTooltip
                axis={axis.key}
                discipline={discipline ?? "lead"}
                targetGrade={targetGrade}
                onClose={() => setOpenTooltip(null)}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
