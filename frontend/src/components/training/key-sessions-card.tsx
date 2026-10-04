"use client";

import { useState } from "react";
import { AlertTriangle, CheckCircle2, CircleDashed, Info, Star, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  formatSessionId,
  hasKeyIssues,
  readDismissed,
  requirementLine,
  shortDay,
  writeDismissed,
} from "@/lib/key-sessions";
import type { KeyProposal, KeyRequirement, KeyStatus } from "@/lib/types";

/**
 * A294 — the key sessions of the week, and what is owed.
 *
 * One row per key stimulus of the phase (finger max, limit, technique, ...).
 * When a key session was skipped or turned into recovery the row says so, and
 * — when the engine found a safe day (finger gap, hard cap, upcoming tests,
 * next week's keys all checked) — offers to re-schedule it with one tap, side
 * effects declared. Deferred / let-go outcomes are told in a neutral tone: not
 * catching up is often the right call, never an alarm.
 *
 * `compact` (on /today): renders nothing when the week is on track.
 */
export function KeySessionsCard({
  status,
  compact = false,
  onApplyProposal,
}: {
  status?: KeyStatus | null;
  compact?: boolean;
  onApplyProposal?: (p: KeyProposal) => Promise<void> | void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  // Dismissed this session (works without storage too: private mode).
  const [dismissed, setDismissed] = useState<string[]>([]);
  if (!status || !status.requirements?.length || status.is_past_week) return null;
  const issues = hasKeyIssues(status);
  if (compact && !issues) return null;

  const weekStart = status.week_start;
  const visibleReqs = status.requirements.filter(
    (r) => !(r.debt > 0 && (dismissed.includes(r.key) || readDismissed(weekStart, r.key))),
  );
  const rows = compact ? visibleReqs.filter((r) => r.debt > 0) : visibleReqs;
  if (compact && rows.length === 0 && status.conflicts.length === 0) return null;

  const tone = status.summary.max_severity === "critical"
    ? "border-danger/40 bg-danger/10"
    : issues
      ? "border-warning/30 bg-warning/5"
      : "border-border";

  return (
    <Card className={cn("gap-0", tone)} data-testid="key-sessions-card">
      <CardContent className="space-y-2 py-3">
        <div className="flex items-center gap-2">
          <Star className="size-4 shrink-0 text-primary" aria-hidden="true" />
          <p className="text-sm font-semibold">Key sessions this week</p>
          <span className="ml-auto text-xs text-muted-foreground tabular-nums">
            {status.summary.covered}/{status.summary.required} on track
          </span>
        </div>

        <ul className="space-y-1.5">
          {rows.map((r) => (
            <RequirementRow
              key={r.key}
              r={r}
              onDismiss={r.debt > 0 ? () => { writeDismissed(weekStart, r.key); setDismissed((d) => [...d, r.key]); } : undefined}
            />
          ))}
        </ul>

        {status.proposals.map((p) => (
          <div key={`${p.date}-${p.slot}-${p.session_id}`} className="rounded-md border border-primary/30 bg-primary/5 p-2 space-y-1">
            <p className="text-sm">
              Re-schedule <span className="font-medium">{p.session_name || formatSessionId(p.session_id)}</span>{" "}
              on <span className="font-medium">{shortDay(p.date)}</span> ({p.slot})
            </p>
            {p.reduced_reentry_dose && (
              <p className="text-xs text-muted-foreground">Re-entry week: limit boulders only, no campus.</p>
            )}
            {p.side_effects.length > 0 ? (
              <p className="text-xs text-warning">
                Also changes:{" "}
                {p.side_effects
                  .map((s) => `${shortDay(s.date)} ${formatSessionId(s.from)} → ${formatSessionId(s.to)}`)
                  .join("; ")}
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">Nothing else in your week changes.</p>
            )}
            {onApplyProposal && (
              <Button
                size="sm"
                className="h-8"
                disabled={busy !== null}
                onClick={async () => {
                  setBusy(p.date);
                  try {
                    await onApplyProposal(p);
                  } finally {
                    setBusy(null);
                  }
                }}
              >
                {busy === p.date ? "Adding…" : "Add to my week"}
              </Button>
            )}
          </div>
        ))}

        {status.conflicts.length > 0 && (
          <ul className="space-y-1">
            {status.conflicts.map((c, i) => (
              <li key={`${c.code}-${c.date}-${i}`} className="flex gap-2 text-xs text-warning">
                <AlertTriangle className="size-3.5 shrink-0 mt-0.5" aria-hidden="true" />
                <span>{c.message}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function RequirementRow({ r, onDismiss }: { r: KeyRequirement; onDismiss?: () => void }) {
  const done = r.status === "done";
  const planned = r.status === "planned" || r.status === "not_due";
  const calm = r.resolution === "deferred_next" || r.resolution === "deferred_fatigue" || r.resolution === "let_go";
  const Icon = done ? CheckCircle2 : planned ? CircleDashed : calm ? Info : AlertTriangle;
  const color = done
    ? "text-success"
    : planned
      ? "text-muted-foreground"
      : calm
        ? "text-muted-foreground"
        : r.severity === "critical"
          ? "text-danger"
          : "text-warning";
  return (
    <li className="flex items-start gap-2 text-sm" title={r.why}>
      <Icon className={cn("size-4 shrink-0 mt-0.5", color)} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <span className="font-medium">{r.label}</span>
        <span className="text-muted-foreground"> — {requirementLine(r)}</span>
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 rounded p-1 text-muted-foreground hover:bg-muted"
          aria-label={`Hide ${r.label} for this week`}
        >
          <X className="size-3.5" />
        </button>
      )}
    </li>
  );
}
