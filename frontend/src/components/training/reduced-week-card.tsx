"use client";

import { useState } from "react";
import { CalendarMinus2 } from "lucide-react";
import { Banner } from "@/components/training/banner";
import {
  readReducedWeekDismissed,
  reducedWeekText,
  shownReducedWeek,
  writeReducedWeekDismissed,
} from "@/lib/reduced-week";
import type { ReducedWeekSuggestion } from "@/lib/types";

/**
 * A330 (D288-FE) — the reduced-week suggestion (A328 (b), D288 R3-b) on /today
 * and on the current week of /week.
 *
 * Present only when `GET /api/week` carries `reduced_week` (it does only when
 * one is suggested). Informational: no button changes the plan — the athlete
 * decides, the coach can build the week on request. Dismissal is local and per
 * suggested week, like the skipped-tests card: a nudge, not a decision that
 * must reach the engine.
 */
export function ReducedWeekCard({ suggestion }: { suggestion?: ReducedWeekSuggestion | null }) {
  const rw = shownReducedWeek(suggestion);
  const [dismissed, setDismissed] = useState<string[]>([]);
  if (!rw) return null;
  if (dismissed.includes(rw.week_start) || readReducedWeekDismissed(rw.week_start)) return null;

  const { lead, rest } = reducedWeekText(rw);
  return (
    <Banner
      tone="info"
      onDismiss={() => {
        writeReducedWeekDismissed(rw.week_start);
        setDismissed((d) => [...d, rw.week_start]);
      }}
    >
      <div className="flex gap-3" data-testid="reduced-week-card">
        <CalendarMinus2 className="size-4 shrink-0 text-info mt-0.5" aria-hidden="true" />
        <p className="min-w-0 leading-snug">
          <span className="font-medium">{lead}</span>
          <span className="text-muted-foreground">{rest}</span>
        </p>
      </div>
    </Banner>
  );
}
