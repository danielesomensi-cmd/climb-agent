"use client";

import type { AssessmentProfile } from "@/lib/types";

const AXES: { key: keyof AssessmentProfile; label: string }[] = [
  { key: "finger_strength", label: "Dita" },
  { key: "pulling_strength", label: "Trazione" },
  { key: "power_endurance", label: "Power End." },
  { key: "technique", label: "Tecnica" },
  { key: "endurance", label: "Resistenza" },
  { key: "body_composition", label: "Composizione" },
];

interface RadarChartProps {
  profile: AssessmentProfile;
  size?: number;
}

export function RadarChart({ profile, size = 280 }: RadarChartProps) {
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

      {/* Legend below */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
        {AXES.map((axis) => (
          <div key={axis.key} className="flex items-center justify-between gap-2">
            <span className="text-muted-foreground">{axis.label}</span>
            <span className="font-mono font-semibold">{profile[axis.key]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
