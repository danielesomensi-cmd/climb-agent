"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useMilestones } from "@/lib/hooks/queries";
import { cn } from "@/lib/utils";
import type { MilestoneItem } from "@/lib/types";

/**
 * A239 (A-GAMIFY-02): milestone gallery on /plan. One-time "firsts" only —
 * no streaks, no volume badges, nothing ever re-locks
 * (docs/design_gamification.md §P3). Locked milestones show dimmed so the
 * road ahead is visible; dynamic grade PBs appear as they're earned.
 */

const TIER_ORDER: Record<string, number> = { activation: 0, medium: 1, career: 2 };

function MilestoneTile({ m }: { m: MilestoneItem }) {
  const label =
    m.context?.grade != null
      ? `${m.name} ${m.context.grade}`
      : m.name;
  return (
    <div
      title={`${label} — ${m.description}${m.unlocked_at ? ` (unlocked ${m.unlocked_at})` : ""}`}
      className={cn(
        "flex flex-col items-center gap-1 rounded-lg border p-2 text-center",
        m.unlocked
          ? "border-amber-700/40 bg-amber-950/30"
          : "border-zinc-800 bg-zinc-900/40 opacity-40 grayscale",
      )}
    >
      <span className="text-2xl" aria-hidden="true">
        {m.icon}
      </span>
      <span className="text-[10px] font-medium leading-tight text-zinc-300">
        {label}
      </span>
    </div>
  );
}

export function MilestonesCard() {
  const { data } = useMilestones();
  const [expanded, setExpanded] = useState(false);
  if (!data) return null;

  const sorted = [...data.milestones].sort((a, b) => {
    if (a.unlocked !== b.unlocked) return a.unlocked ? -1 : 1;
    return (TIER_ORDER[a.tier] ?? 9) - (TIER_ORDER[b.tier] ?? 9);
  });
  const visible = expanded ? sorted : sorted.slice(0, 8);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Milestones</CardTitle>
          <span className="text-xs text-muted-foreground">
            {data.unlocked_count} unlocked
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-4 gap-2">
          {visible.map((m) => (
            <MilestoneTile key={m.id} m={m} />
          ))}
        </div>
        {sorted.length > 8 && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="flex w-full items-center justify-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            {expanded ? (
              <>
                Show less <ChevronUp className="size-3" />
              </>
            ) : (
              <>
                Show all ({sorted.length}) <ChevronDown className="size-3" />
              </>
            )}
          </button>
        )}
      </CardContent>
    </Card>
  );
}
