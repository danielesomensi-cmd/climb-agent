"use client";

import { useState } from "react";
import { AlertTriangle, CheckCircle2, ChevronRight, CircleDashed, Info, Star, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  formatSessionId,
  hasKeyIssues,
  readDismissed,
  replacedBy,
  requirementLine,
  shortDay,
  whenLabel,
  writeDismissed,
} from "@/lib/key-sessions";
import type { KeyProposal, KeyRequirement, KeyStatus, KeyTopup } from "@/lib/types";

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
 * A325 — a technique dose one drill short says which drill is owed, and the
 * catch-up is that drill added to a planned session (`topups`), not a whole
 * session replaced. A re-schedule that takes another session's place says so
 * once: "Swap A for B".
 *
 * `compact` (on /today): renders nothing when the week is on track.
 * `collapsible` (A308, /today): a one-line summary that opens on tap — open
 * from the start only when there is a re-schedule to accept or a critical row.
 */
export function KeySessionsCard({
  status,
  compact = false,
  collapsible = false,
  onApplyProposal,
  onApplyTopup,
}: {
  status?: KeyStatus | null;
  compact?: boolean;
  collapsible?: boolean;
  onApplyProposal?: (p: KeyProposal) => Promise<void> | void;
  /** A325: add the one missing technique drill to a planned session. */
  onApplyTopup?: (t: KeyTopup) => Promise<void> | void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  // Dismissed this session (works without storage too: private mode).
  const [dismissed, setDismissed] = useState<string[]>([]);
  const [open, setOpen] = useState<boolean | null>(null);
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

  // A325: a top-up follows its row — hidden with it when dismissed.
  const topups = (status.topups ?? []).filter((t) => visibleReqs.some((r) => r.key === t.key));
  const urgent =
    status.proposals.length > 0 || topups.length > 0 || status.requirements.some((r) => r.severity === "critical");
  const expanded = !collapsible || (open ?? urgent);

  const header = (
    <>
      <Star className="size-4 shrink-0 text-primary" aria-hidden="true" />
      <p className="text-sm font-semibold">Key sessions this week</p>
      <span className="ml-auto text-xs text-muted-foreground tabular-nums">
        {status.summary.covered}/{status.summary.required} on track
      </span>
    </>
  );

  return (
    <Card className={cn("gap-0", tone)} data-testid="key-sessions-card">
      <CardContent className={cn("space-y-2", collapsible ? "py-1" : "py-3")}>
        {collapsible ? (
          <button
            type="button"
            aria-expanded={expanded}
            onClick={() => setOpen(!expanded)}
            className="flex min-h-11 w-full items-center gap-2 text-left"
          >
            {header}
            <ChevronRight
              className={cn("size-4 shrink-0 text-muted-foreground transition-transform", expanded && "rotate-90")}
              aria-hidden="true"
            />
          </button>
        ) : (
          <div className="flex items-center gap-2">{header}</div>
        )}

        {expanded && (
          <>
            <ul className="space-y-1.5">
              {rows.map((r) => (
                <RequirementRow
                  key={r.key}
                  r={r}
                  onDismiss={r.debt > 0 ? () => { writeDismissed(weekStart, r.key); setDismissed((d) => [...d, r.key]); } : undefined}
                />
              ))}
            </ul>

            {topups.map((t) => {
              const id = `topup:${t.date}-${t.slot}-${t.exercise_id}`;
              return (
                <div key={id} className="rounded-md border border-primary/30 bg-primary/5 p-2 space-y-1" data-testid="key-topup">
                  <p className="text-sm">
                    Add <span className="font-medium">{t.exercise_name}</span> to{" "}
                    <span className="font-medium">{t.session_name || formatSessionId(t.session_id)}</span>{" "}
                    — {whenLabel(t.date, t.slot)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    One drill, right after the warm-up. The rest of the session stays as it is.
                  </p>
                  {onApplyTopup && (
                    <Button
                      size="sm"
                      className="min-h-[44px]"
                      disabled={busy !== null}
                      onClick={async () => {
                        setBusy(id);
                        try {
                          await onApplyTopup(t);
                        } finally {
                          setBusy(null);
                        }
                      }}
                    >
                      {busy === id ? "Adding…" : "Add the drill"}
                    </Button>
                  )}
                </div>
              );
            })}

            {status.proposals.map((p) => {
              const id = `${p.date}-${p.slot}-${p.session_id}`;
              const name = p.session_name || formatSessionId(p.session_id);
              // A325: the session it takes the place of is said once, in the
              // headline — the other side effects stay listed below.
              const replaced = replacedBy(p);
              const others = p.side_effects.filter((s) => s !== replaced);
              return (
                <div key={id} className="rounded-md border border-primary/30 bg-primary/5 p-2 space-y-1" data-testid="key-proposal">
                  <p className="text-sm">
                    {replaced ? (
                      <>
                        Swap <span className="font-medium">{formatSessionId(replaced.from)}</span> for{" "}
                        <span className="font-medium">{name}</span>
                      </>
                    ) : (
                      <>
                        Add <span className="font-medium">{name}</span>
                      </>
                    )}{" "}
                    — {whenLabel(p.date, p.slot)}
                  </p>
                  {p.reduced_reentry_dose && (
                    <p className="text-xs text-muted-foreground">Re-entry week: limit boulders only, no campus.</p>
                  )}
                  {others.length > 0 ? (
                    <p className="text-xs text-warning">
                      Also changes:{" "}
                      {others
                        .map((s) => `${shortDay(s.date)} ${formatSessionId(s.from)} → ${formatSessionId(s.to)}`)
                        .join("; ")}
                    </p>
                  ) : (
                    <p className="text-xs text-muted-foreground">Nothing else in your week changes.</p>
                  )}
                  {onApplyProposal && (
                    <Button
                      size="sm"
                      className="min-h-[44px]"
                      disabled={busy !== null}
                      onClick={async () => {
                        setBusy(id);
                        try {
                          await onApplyProposal(p);
                        } finally {
                          setBusy(null);
                        }
                      }}
                    >
                      {busy === id ? (replaced ? "Swapping…" : "Adding…") : replaced ? "Swap sessions" : "Add to my week"}
                    </Button>
                  )}
                </div>
              );
            })}

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
          </>
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
          className="-my-2 -mr-2 flex size-11 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-muted"
          aria-label={`Hide ${r.label} for this week`}
        >
          <X className="size-3.5" />
        </button>
      )}
    </li>
  );
}
