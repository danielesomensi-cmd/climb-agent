"use client";

import { useState } from "react";
import { Gauge, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { RetestActions } from "@/components/training/retest-actions";
import { apiErrorDetail, undoRetestDecline } from "@/lib/api";
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
 *
 * B414 (B414-4, model A): a real test counts at any age. Each axis says until
 * when its max is valid (or «extended to», after a postpone), and the card
 * carries the two choices of the Today expiry card — «Do the test», «Postpone
 * the expiry» — plus «Undo postpone» on an axis with an active postpone. No
 * «Not now» (A320-FE superseded): a decline stays with the API / the coach.
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
  pain: "pain reported on this zone in the last 7 days",
};

const NO_TEST_TEXT: Record<string, string> = {
  "blocked:phase": "no test in the performance and deload phases",
  "blocked:gap": "not before the minimum gap since the last test",
  "blocked:trip": "trip window: the test waits until after",
  "blocked:very_hard": "waiting for 3 easier days",
  "blocked:pain": "pain reported on this zone: the test waits until it settles",
  not_due_within_horizon: "not due in the coming weeks",
  no_placement_slot: "this week's plan had no day that fit it",
  // A319-FE: after A319 the pull-up test goes on the hang test's day (pair,
  // combined test, or the day of a kept test) and needs weights there.
  "blocked:no_paired_slot": "the pull-up test needs the hang test's day, with weights there: it waits for its next turn",
  not_in_plan: "this week's plan was built without it",
  missed: "the planned test this week was not done",
  "deferred:earlier_week": "it belongs to an earlier week",
  // B414: no test is due after the end of the macrocycle.
  after_cycle_end: "the cycle ends first — the next cycle opens with the tests",
  // A320: the athlete's own word (API / coach).
  declined: "you declined this test: it comes back with your next test or a new reason to test",
  postponed: "you postponed it",
  not_tested_recently: "not scheduled by the retest policy",
};

/** A320 / B414: the active postpone of an axis, if any. */
function activePostpone(s: RetestAxisStatus) {
  return (s.declines ?? []).find((d) => d.kind === "postpone") ?? null;
}

function noTestText(s: RetestAxisStatus): string {
  const reason = s.next_test_reason ?? "";
  if (reason === "postponed") {
    const until = activePostpone(s)?.until;
    return until ? `you postponed it to ${formatDateShort(until)}` : NO_TEST_TEXT.postponed;
  }
  return NO_TEST_TEXT[reason] ?? "not due yet";
}

/** B414: until when the max is valid — information only, nothing stops after it. */
function validityText(s: RetestAxisStatus): string | null {
  if (!s.covered || !s.valid_until) return null;
  const day = formatDateShort(s.valid_until);
  if (s.expired) return `Expired after ${day} — your ladders and loads keep going`;
  if (s.extended) return `Extended to ${day}`;
  return `Valid until ${day}`;
}

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
      {validityText(s) && (
        <p className={`text-xs ${s.expired || s.expiring ? "text-warning" : "text-muted-foreground"}`}>
          {validityText(s)}
        </p>
      )}
      {s.request && (
        <p className="text-xs text-muted-foreground">
          You asked for the test{s.request.requested_at ? ` on ${formatDateShort(s.request.requested_at)}` : ""}.
        </p>
      )}
      {next ? (
        <p className="text-xs text-muted-foreground">
          {next.source === "planned" ? "Next test" : "Next test from"}{" "}
          <span className="font-medium text-foreground">{formatDateShort(next.date)}</span>
          {next.reason ? ` — ${next.reason}` : ""}
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">
          {s.covered
            ? `No test scheduled: ${noTestText(s)}.`
            : "Not scheduled by the retest policy: the periodic test reminder covers it."}
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

function retestAxes(status?: RetestStatus | null): RetestAxisStatus[] {
  if (!status) return [];
  return (["finger", "pulling"] as RetestAxis[])
    .map((a) => status.axes[a])
    .filter((s): s is RetestAxisStatus => Boolean(s));
}

/** A308 — whether the card renders anything (the /week notes count). */
export function retestStatusVisible(status?: RetestStatus | null): boolean {
  return retestAxes(status).length > 0;
}

/** B414: «Undo postpone» of one axis — a dry run shows the validity it goes back to. */
function UndoPostpone({ s, onChanged }: { s: RetestAxisStatus; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function check() {
    setBusy(true);
    setError(null);
    try {
      const res = await undoRetestDecline(s.axis, true);
      const back = res.retest_status?.axes[s.axis]?.valid_until;
      setPreview(back ? `Your max goes back to valid until ${formatDateShort(back)}.` : "The postpone is removed.");
    } catch (err) {
      setError(apiErrorDetail(err, "Couldn't check your plan. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await undoRetestDecline(s.axis, false);
      toast.success("Postpone undone.");
      setPreview(null);
      onChanged();
    } catch (err) {
      setError(apiErrorDetail(err, "Couldn't save your choice. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-1">
      {preview ? (
        <div className="space-y-2 rounded-lg border p-2">
          <p className="text-xs">{preview}</p>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" className="min-h-[44px] flex-1" disabled={busy} onClick={() => setPreview(null)}>
              Keep it
            </Button>
            <Button variant="outline" size="sm" className="min-h-[44px] flex-1" disabled={busy} onClick={() => void confirm()}>
              Undo postpone
            </Button>
          </div>
        </div>
      ) : (
        <Button
          variant="ghost"
          size="sm"
          className="min-h-[44px] px-2 text-xs text-muted-foreground"
          disabled={busy}
          onClick={() => void check()}
        >
          Undo postpone ({AXIS_LABEL[s.axis]})
        </Button>
      )}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

export function RetestStatusCard({
  status,
  onChanged,
}: {
  status?: RetestStatus | null;
  /** B414: a choice was saved (request, postpone, undo) — reload the week. */
  onChanged?: () => void;
}) {
  if (!status) return null;
  const axes = retestAxes(status);
  if (axes.length === 0) return null;
  const covered = axes.filter((s) => s.covered);

  return (
    <Card>
      <CardContent className="flex gap-3 py-3">
        <Gauge className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="min-w-0 flex-1 space-y-3">
          <p className="text-sm font-semibold">Your tested maxes</p>
          {axes.map((s) => (
            <AxisLine key={s.axis} s={s} />
          ))}
          {onChanged && covered.length > 0 && (
            <>
              <RetestActions onChanged={onChanged} />
              {covered
                .filter((s) => activePostpone(s))
                .map((s) => (
                  <UndoPostpone key={s.axis} s={s} onChanged={onChanged} />
                ))}
            </>
          )}
          <p className="text-[11px] text-muted-foreground">
            Changes under {status.stable_band_pct}% between two tests count as stable. Feedback
            moves your working loads, never your max: only a test does.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
