"use client";

import { useState, useRef, useEffect } from "react";
import { Info } from "lucide-react";
import type { AssessmentProfile } from "@/lib/types";
import { getRadarLabels, getAxisDescription, type Discipline } from "@/lib/gradeUtils";

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
}

function AxisTooltip({
  axis,
  discipline,
  onClose,
}: {
  axis: string;
  discipline: Discipline;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [onClose]);

  const info = getAxisDescription(axis, discipline);
  if (!info) return null;

  return (
    <div
      ref={ref}
      className="absolute z-50 w-72 rounded-lg border border-border bg-background p-3 shadow-lg text-sm"
      style={{ left: "50%", transform: "translateX(-50%)", top: "100%" }}
    >
      <p className="font-semibold mb-1">{info.label}</p>
      <p className="text-muted-foreground text-xs leading-relaxed mb-2">{info.description}</p>
      <p className="text-xs">
        <span className="text-muted-foreground">Low score means: </span>
        <span className="text-muted-foreground/80 italic">{info.low}</span>
      </p>
    </div>
  );
}

export function RadarChart({ profile, size = 280, discipline }: RadarChartProps) {
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
            <span className="font-mono font-semibold">{profile[axis.key]}</span>
            {openTooltip === axis.key && (
              <AxisTooltip
                axis={axis.key}
                discipline={discipline ?? "lead"}
                onClose={() => setOpenTooltip(null)}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
