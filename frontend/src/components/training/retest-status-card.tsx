"use client";

import { Gauge, AlertTriangle } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { formatDateShort } from "@/lib/format";
import type { RetestAxis, RetestAxisStatus, RetestBlocker, RetestStatus } from "@/lib/types";

/**
 * A289 — where the athlete's tested maxes stand and when the next test is.
 *
 * One line per tested axis: official max (test date, confidence), the trend vs
 * the previous test (|Δ| under the stable band reads "stable"), and the next
 * test with its reason. The policy (`retest_policy`) decides tests by itself,
 * so this is information, not a decision: nothing here writes to the engine.
 *
 * `blockers` are live flags on a test already in the plan (e.g. a very_hard
 * session logged since, or a custom finger session added 2 days before). The
 * engine does NOT move the test on its own (decision 2026-10-04): it says so,
 * and the athlete decides.
 */
const AXIS_LABEL: Record<RetestAxis, string> = {
  finger: "Finger max (7\" hang)",
  pulling: "Pull-up 2RM",
};

const BLOCKER_TEXT: Record<string, string> = {
  very_hard: "a very hard session in the 3 days before",
  trip: "it falls within 10 days of a trip",
  recent_finger: "a hard finger day less than 72 h before",
  heavy_pull: "heavy pulling less than 48 h before",
};

const NO_TEST_TEXT: Record<string, string> = {
  "blocked:phase": "no test in the performance and deload phases",
  "blocked:gap": "not before the minimum gap since the last test",
  "blocked:trip": "trip window: the test waits until after",
  "blocked:very_hard": "waiting for 3 easier days",
  not_due_within_horizon: "not due in the coming weeks",
};

function trendText(s: RetestAxisStatus): string | null {
  if (!s.trend || s.delta_pct === null) return null;
  const sign = s.delta_pct > 0 ? "+" : "";
  const label = s.trend === "stable" ? "stable" : s.trend === "up" ? "up" : "down";
  return `${label} (${sign}${s.delta_pct}%)`;
}

function blockerText(b: RetestBlocker): string {
  return BLOCKER_TEXT[b.code] ?? b.code;
}

function AxisLine({ s }: { s: RetestAxisStatus }) {
  const trend = trendText(s);
  const next = s.next_test;
  return (
    <div className="space-y-0.5">
      <p className="text-sm font-medium">
        {AXIS_LABEL[s.axis]}: {s.official_total_kg} kg
      </p>
      <p className="text-xs text-muted-foreground">
        Tested {formatDateShort(s.test_date)} · {s.confidence} confidence
        {trend ? ` · ${trend}` : ""}
      </p>
      {next ? (
        <p className="text-xs text-muted-foreground">
          {next.source === "planned" ? "Next test" : "Next test from"}{" "}
          <span className="font-medium text-foreground">{formatDateShort(next.date)}</span>
          {next.reason ? ` — ${next.reason}` : ""}
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">
          {s.covered
            ? `No test scheduled: ${NO_TEST_TEXT[s.next_test_reason ?? ""] ?? "not due yet"}.`
            : "Test older than 90 days: the plan schedules a fresh one at the end of a phase."}
        </p>
      )}
      {next && next.blockers.length > 0 ? (
        <p className="flex items-start gap-1 text-xs text-warning">
          <AlertTriangle className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
          <span>
            Heads-up: {next.blockers.map(blockerText).join("; ")}. The test stays where it is —
            move it if you are not fresh.
          </span>
        </p>
      ) : null}
      {s.fatigue ? (
        <p className="flex items-start gap-1 text-xs text-warning">
          <AlertTriangle className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
          <span>3 hard sessions in 14 days: loads held at the phase floor.</span>
        </p>
      ) : null}
    </div>
  );
}

export function RetestStatusCard({ status }: { status?: RetestStatus | null }) {
  if (!status) return null;
  const axes = (["finger", "pulling"] as RetestAxis[])
    .map((a) => status.axes[a])
    .filter((s): s is RetestAxisStatus => Boolean(s));
  if (axes.length === 0) return null;

  return (
    <Card>
      <CardContent className="flex gap-3 py-3">
        <Gauge className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="min-w-0 flex-1 space-y-3">
          <p className="text-sm font-semibold">Your tested maxes</p>
          {axes.map((s) => (
            <AxisLine key={s.axis} s={s} />
          ))}
          <p className="text-[11px] text-muted-foreground">
            Changes under {status.stable_band_pct}% between two tests count as stable. Feedback
            moves your working loads, never your max: only a test does.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
