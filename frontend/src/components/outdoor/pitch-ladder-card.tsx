"use client";

/**
 * A265 — the day's pitch ladder on the plan card.
 *
 * Read mode is the one that matters: it has to be legible at the base of a
 * route, on a phone, in the sun — so it is a plain table of grade / attempts /
 * rest, not a chart. Edit mode is deliberately dumb (text + number inputs):
 * the athlete standing at the crag knows better than the generator, and every
 * field the generator fills must be overridable.
 */

import { useState } from "react";
import { Mountain, Pencil, Plus, RefreshCw, Trash2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { normaliseLadder } from "@/lib/pitch-ladder";
import type {
  OutdoorDayType,
  OutdoorPitchLadder,
  PitchLadderRow,
  PitchRole,
} from "@/lib/types";

const ROLE_LABEL: Record<PitchRole, string> = {
  warmup: "Warm-up",
  build: "Build",
  main: "Main",
  power_endurance: "Power endurance",
  cooldown: "Cool-down",
};

const ROLE_STYLE: Record<PitchRole, string> = {
  warmup: "text-sky-600 dark:text-sky-400",
  build: "text-amber-600 dark:text-amber-400",
  main: "text-red-600 dark:text-red-400",
  power_endurance: "text-violet-600 dark:text-violet-400",
  cooldown: "text-emerald-600 dark:text-emerald-400",
};

const DAY_TYPES: Array<{ id: OutdoorDayType; label: string; hint: string }> = [
  { id: "onsight_flash", label: "Onsight", hint: "Push the ceiling, one try per route" },
  { id: "project", label: "Project", hint: "Burns on something at your limit" },
  { id: "volume", label: "Volume", hint: "Many sub-max pitches, active rest" },
  { id: "scout_easy", label: "Scout", hint: "Easy recon, information not performance" },
];

interface Props {
  plan?: OutdoorPitchLadder;
  /** Generate a fresh ladder from the athlete's grades, for a day type. */
  onGenerate?: (dayType: OutdoorDayType) => void;
  onSave?: (plan: OutdoorPitchLadder | null) => void;
  generating?: boolean;
  saving?: boolean;
  /** Completed days are immutable — read-only, no edit affordances. */
  readOnly?: boolean;
}

function emptyRow(index: number): PitchLadderRow {
  return { index, role: "main", grade: "", attempts: 1, rest_after_min: 10 };
}

export function PitchLadderCard({
  plan,
  onGenerate,
  onSave,
  generating,
  saving,
  readOnly,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [rows, setRows] = useState<PitchLadderRow[]>([]);

  const startEdit = () => {
    setRows(plan?.pitches?.length ? plan.pitches.map((p) => ({ ...p })) : [emptyRow(1)]);
    setEditing(true);
  };

  const patch = (i: number, field: keyof PitchLadderRow, value: string | number) =>
    setRows((prev) =>
      prev.map((r, idx) => (idx === i ? { ...r, [field]: value } : r)),
    );

  const save = () => {
    onSave?.(normaliseLadder(rows, plan));
    setEditing(false);
  };

  // ── Empty state ──────────────────────────────────────────────────────────
  if (!plan?.pitches?.length && !editing) {
    if (readOnly) return null;
    return (
      <div className="mt-2 rounded-md border border-dashed border-muted-foreground/30 p-3">
        <p className="text-xs text-muted-foreground mb-2">
          No plan for this day yet. Pick what kind of day it is — grades and
          rests come from your own onsight and redpoint.
        </p>
        <div className="flex flex-wrap gap-1.5 mb-2">
          {DAY_TYPES.map((dt) => (
            <Button
              key={dt.id}
              size="sm"
              variant="outline"
              className="text-xs"
              title={dt.hint}
              onClick={() => onGenerate?.(dt.id)}
              disabled={generating || !onGenerate}
            >
              <Mountain className={cn("size-3 mr-1", generating && "animate-pulse")} />
              {dt.label}
            </Button>
          ))}
        </div>
        <Button size="sm" variant="ghost" className="text-xs" onClick={startEdit}>
          <Pencil className="size-3 mr-1" />
          Write it myself
        </Button>
      </div>
    );
  }

  // ── Edit mode ────────────────────────────────────────────────────────────
  if (editing) {
    return (
      <div className="mt-2 rounded-md border p-3 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium">Edit the plan</span>
          <Button size="sm" variant="ghost" className="text-xs" onClick={() => setEditing(false)}>
            <X className="size-3 mr-1" />
            Cancel
          </Button>
        </div>

        <div className="grid grid-cols-[1fr_3.5rem_4rem_2rem] gap-1 text-[10px] text-muted-foreground px-1">
          <span>Grade</span>
          <span>Burns</span>
          <span>Rest&apos;</span>
          <span />
        </div>

        {rows.map((r, i) => (
          <div key={i} className="grid grid-cols-[1fr_3.5rem_4rem_2rem] gap-1 items-center">
            <Input
              value={r.grade}
              onChange={(e) => patch(i, "grade", e.target.value)}
              placeholder="7a+"
              className="h-8 text-xs"
            />
            <Input
              type="number"
              min={1}
              value={r.attempts}
              onChange={(e) => patch(i, "attempts", Number(e.target.value))}
              className="h-8 text-xs"
            />
            <Input
              type="number"
              min={0}
              value={r.rest_after_min}
              onChange={(e) => patch(i, "rest_after_min", Number(e.target.value))}
              className="h-8 text-xs"
            />
            <Button
              size="sm"
              variant="ghost"
              className="h-8 w-8 p-0 text-muted-foreground"
              onClick={() => setRows((prev) => prev.filter((_, idx) => idx !== i))}
              aria-label={`Remove pitch ${i + 1}`}
            >
              <Trash2 className="size-3.5" />
            </Button>
          </div>
        ))}

        <div className="flex gap-2 pt-1">
          <Button
            size="sm"
            variant="outline"
            className="text-xs"
            onClick={() => setRows((prev) => [...prev, emptyRow(prev.length + 1)])}
          >
            <Plus className="size-3 mr-1" />
            Add pitch
          </Button>
          <Button size="sm" className="text-xs ml-auto" onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save plan"}
          </Button>
        </div>
      </div>
    );
  }

  // ── Read mode ────────────────────────────────────────────────────────────
  const pitches = plan!.pitches;
  return (
    <div className="mt-2 rounded-md border p-3">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-medium">Plan for the day</span>
        {plan!.summary && (
          <Badge variant="outline" className="text-[10px]">
            {plan!.summary.pitch_count} pitches · {plan!.summary.total_attempts} burns · ~
            {plan!.summary.estimated_hours}h
          </Badge>
        )}
        {plan!.generated === false && (
          <Badge variant="secondary" className="text-[10px]">Edited</Badge>
        )}
        {!readOnly && (
          <div className="ml-auto flex gap-1">
            {onGenerate && plan!.day_type && (
              <Button
                size="sm"
                variant="ghost"
                className="h-7 px-2 text-xs text-muted-foreground"
                onClick={() => {
                  // A hand-edited ladder is the athlete's, not ours — never
                  // overwrite it without asking.
                  if (
                    plan!.generated === false &&
                    !window.confirm("Regenerate? Your hand-edited plan will be replaced.")
                  ) {
                    return;
                  }
                  onGenerate(plan!.day_type!);
                }}
                disabled={generating}
                aria-label="Regenerate plan"
              >
                <RefreshCw className={cn("size-3.5", generating && "animate-spin")} />
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              className="h-7 px-2 text-xs text-muted-foreground"
              onClick={startEdit}
              aria-label="Edit plan"
            >
              <Pencil className="size-3.5" />
            </Button>
          </div>
        )}
      </div>

      <ol className="space-y-1.5">
        {pitches.map((p) => (
          <li key={p.index} className="flex items-baseline gap-2 text-xs">
            <span className="w-4 shrink-0 text-muted-foreground tabular-nums">{p.index}.</span>
            <span className="w-12 shrink-0 font-semibold tabular-nums">{p.grade}</span>
            <span className="w-8 shrink-0 text-muted-foreground tabular-nums">
              ×{p.attempts}
            </span>
            <span className="w-14 shrink-0 text-muted-foreground tabular-nums">
              {p.rest_after_min > 0 ? `rest ${p.rest_after_min}'` : "—"}
            </span>
            <span className={cn("shrink-0 text-[10px] uppercase tracking-wide", ROLE_STYLE[p.role])}>
              {ROLE_LABEL[p.role] ?? p.role}
            </span>
          </li>
        ))}
      </ol>

      {pitches.some((p) => p.note) && (
        <ul className="mt-2 space-y-1 border-t pt-2">
          {pitches
            .filter((p) => p.note)
            .map((p) => (
              <li key={`n-${p.index}`} className="text-[11px] text-muted-foreground">
                <span className="font-medium tabular-nums">{p.index}. {p.grade}</span> — {p.note}
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}
