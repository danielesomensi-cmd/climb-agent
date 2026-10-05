"use client";

import { AlertTriangle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { describeUnmetSecondary, weekAlerts } from "@/lib/week-alerts";
import type { GuardWarning, WeekPlan } from "@/lib/types";

/**
 * A300 + A301 — the alerts of the week (or of one day on /today).
 *
 * Since A301 the recovery guards never rewrite the plan after a user action:
 * "se voglio fare sovrallenamento lo faccio, decisione mia, tu solo segnala
 * alert". This card is where they are said out loud — the `guard_warnings`
 * sibling of the week, the lunch-rotation rules the week breaks
 * (`secondary_warnings`) and the complementary slots that stayed free
 * (`unmet_secondary`, /week only). Informative tone: nothing was blocked,
 * nothing was downgraded, the athlete decides.
 */
export function WeekAlertsCard({
  guardWarnings,
  weekPlan,
  date,
  compact = false,
}: {
  guardWarnings?: GuardWarning[] | null;
  weekPlan?: WeekPlan | null;
  /** Only the alerts of this day (/today). */
  date?: string;
  compact?: boolean;
}) {
  const alerts = weekAlerts(guardWarnings, weekPlan, date);
  const unmet = date
    ? (weekPlan?.unmet_secondary ?? []).filter((u) => u.date === date)
    : (weekPlan?.unmet_secondary ?? []);
  if (alerts.length === 0 && unmet.length === 0) return null;

  const heading = date
    ? alerts.length === 1 ? "1 alert today" : `${alerts.length} alerts today`
    : alerts.length === 1 ? "1 alert this week" : `${alerts.length} alerts this week`;

  return (
    <Card className="border-warning/30 bg-warning/10" data-testid="week-alerts-card">
      <CardContent className="flex gap-3 py-3">
        <AlertTriangle className="size-4 shrink-0 text-warning mt-0.5" aria-hidden="true" />
        <div className="min-w-0 space-y-2">
          {alerts.length > 0 && (
            <div className="space-y-1">
              <p className="text-sm font-medium text-warning">{heading}</p>
              {!compact && (
                <p className="text-xs text-muted-foreground">
                  A heads-up, not a change: your sessions stay as planned. Adjust
                  them yourself if you want to.
                </p>
              )}
              <ul className="space-y-1">
                {alerts.map((a, i) => (
                  <li key={`${a.source}-${a.code}-${a.date}-${a.slot}-${i}`} className="text-xs leading-snug">
                    <span className="font-medium">{a.title}</span>
                    {!date && <span className="text-muted-foreground"> · {a.date}{a.slot ? ` ${a.slot}` : ""}</span>}
                    <span className="block text-muted-foreground">{a.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {unmet.length > 0 && (
            <div className="space-y-1">
              <p className="text-sm font-medium text-warning">Complementary slots left free</p>
              <ul className="space-y-0.5">
                {unmet.map((u, i) => (
                  <li key={`${u.reason}-${u.date}-${u.slot}-${u.focus}-${i}`} className="text-xs text-muted-foreground leading-snug">
                    {describeUnmetSecondary(u)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
