"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  apiErrorDetail,
  extendRetest,
  requestRetest,
  type RetestExtendResponse,
  type RetestRequestResponse,
} from "@/lib/api";
import { formatDateShort } from "@/lib/format";
import type { RetestAxis, RetestAxisStatus, RetestStatus } from "@/lib/types";

/**
 * B414 (B414-4) — the only two ways out of a test that expires (Daniele,
 * 07/11, model A): «Do the test» and «Postpone the expiry». Nothing switches
 * off at the expiry — ladders, anchored loads, phase rotation and coach keep
 * going — so these are proposals, never a gate. There is no «Not now» in the
 * app (A320-FE superseded): a decline stays with the API / the coach.
 *
 * Both run a dry run first and show what would change, then the athlete
 * confirms. An endpoint error is always shown: nothing pretends to be saved.
 */
export const EXTENSION_WEEKS = [2, 4, 6] as const;
export const DEFAULT_EXTENSION_WEEKS = 4;

const AXIS_NAME: Record<RetestAxis, string> = { finger: "finger", pulling: "pull-up" };

/** "finger and pull-up" — the covered axes, in the policy's order. */
export function axesLabel(axes: RetestAxis[]): string {
  const names = (["finger", "pulling"] as RetestAxis[]).filter((a) => axes.includes(a)).map((a) => AXIS_NAME[a]);
  return names.length === 2 ? `${names[0]} and ${names[1]}` : names[0] ?? "";
}

export function coveredAxes(status?: RetestStatus | null): RetestAxisStatus[] {
  if (!status) return [];
  return (["finger", "pulling"] as RetestAxis[])
    .map((a) => status.axes[a])
    .filter((s): s is RetestAxisStatus => !!s && s.covered);
}

type Preview =
  | { kind: "request"; res: RetestRequestResponse }
  | { kind: "extend"; res: RetestExtendResponse; weeks: number };

function requestSummary(res: RetestRequestResponse): string {
  if (res.action === "already_planned") {
    return `Already in your plan${res.go_to ? ` on ${formatDateShort(res.go_to)}` : ""}.`;
  }
  if (res.action === "cycle_ended") {
    return "Your cycle is over: the next one opens with the tests.";
  }
  return res.go_to
    ? `The test goes on ${formatDateShort(res.go_to)} — the first day your recent sessions allow.`
    : "The test goes on the first day your recent sessions allow (the plan will show it).";
}

function extendSummary(res: RetestExtendResponse): string {
  const removed = res.tests_removed.length;
  return (
    `Your max stays valid until ${formatDateShort(res.until)}.` +
    (removed === 1 ? " The planned test leaves the plan." : removed > 1 ? ` ${removed} planned tests leave the plan.` : "")
  );
}

export function RetestActions({
  onChanged,
  onCycleEnded,
}: {
  /** A choice was saved: reload the week (and the status with it). */
  onChanged: () => void;
  /** "Do the test" after the end of the cycle: open "Start a new cycle" (Today). */
  onCycleEnded?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [choosingWeeks, setChoosingWeeks] = useState(false);
  const [weeks, setWeeks] = useState<number>(DEFAULT_EXTENSION_WEEKS);
  const [preview, setPreview] = useState<Preview | null>(null);

  async function run<T>(fn: () => Promise<T>, fallback: string): Promise<T | null> {
    if (busy) return null;
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (err) {
      setError(apiErrorDetail(err, fallback));
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function previewRequest() {
    setChoosingWeeks(false);
    const res = await run(() => requestRetest({ dry_run: true }), "Couldn't check your plan. Please try again.");
    if (res) setPreview({ kind: "request", res });
  }

  async function previewExtend() {
    const res = await run(() => extendRetest({ weeks, dry_run: true }), "Couldn't check your plan. Please try again.");
    if (res) {
      setChoosingWeeks(false);
      setPreview({ kind: "extend", res, weeks });
    }
  }

  async function confirm() {
    if (!preview) return;
    if (preview.kind === "request") {
      const res = await run(() => requestRetest({}), "Couldn't save your choice. Please try again.");
      if (!res) return;
      if (res.action === "cycle_ended") {
        setPreview(null);
        onCycleEnded?.();
        return;
      }
      toast.success(
        res.action === "already_planned"
          ? "The test is already in your plan."
          : res.go_to
            ? `Test requested — it goes on ${formatDateShort(res.go_to)}.`
            : "Test requested — the plan places it on the first day that fits.",
      );
    } else {
      const res = await run(() => extendRetest({ weeks: preview.weeks }), "Couldn't save your choice. Please try again.");
      if (!res) return;
      toast.success(`Expiry postponed — your max is valid until ${formatDateShort(res.until)}.`);
    }
    setPreview(null);
    onChanged();
  }

  const requestNeedsNoConfirm = preview?.kind === "request" && preview.res.action === "already_planned";

  return (
    <div className="space-y-2">
      {!preview && !choosingWeeks && (
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button className="min-h-[44px] flex-1" disabled={busy} onClick={() => void previewRequest()}>
            Do the test
          </Button>
          <Button
            variant="outline"
            className="min-h-[44px] flex-1"
            disabled={busy}
            onClick={() => {
              setError(null);
              setChoosingWeeks(true);
            }}
          >
            Postpone the expiry
          </Button>
        </div>
      )}

      {choosingWeeks && (
        <div className="space-y-2 rounded-lg border p-3">
          <p className="text-sm">Postpone the expiry of your max by</p>
          <div className="flex gap-2" role="radiogroup" aria-label="Weeks">
            {EXTENSION_WEEKS.map((w) => (
              <Button
                key={w}
                type="button"
                role="radio"
                aria-checked={weeks === w}
                variant={weeks === w ? "default" : "outline"}
                className="min-h-[44px] flex-1"
                onClick={() => setWeeks(w)}
              >
                {w} weeks
              </Button>
            ))}
          </div>
          <div className="flex gap-2">
            <Button variant="ghost" className="min-h-[44px] flex-1" disabled={busy} onClick={() => setChoosingWeeks(false)}>
              Cancel
            </Button>
            <Button className="min-h-[44px] flex-1" disabled={busy} onClick={() => void previewExtend()}>
              {busy ? "Checking…" : "Continue"}
            </Button>
          </div>
        </div>
      )}

      {preview && (
        <div className="space-y-2 rounded-lg border p-3">
          <p className="text-sm">
            {preview.kind === "request" ? requestSummary(preview.res) : extendSummary(preview.res)}
          </p>
          <div className="flex gap-2">
            <Button variant="ghost" className="min-h-[44px] flex-1" disabled={busy} onClick={() => setPreview(null)}>
              {requestNeedsNoConfirm ? "OK" : "Cancel"}
            </Button>
            {!requestNeedsNoConfirm &&
              (preview.kind === "request" && preview.res.action === "cycle_ended" ? (
                onCycleEnded ? (
                  <Button
                    className="min-h-[44px] flex-1"
                    onClick={() => {
                      setPreview(null);
                      onCycleEnded();
                    }}
                  >
                    Start a new cycle
                  </Button>
                ) : null
              ) : (
                <Button className="min-h-[44px] flex-1" disabled={busy} onClick={() => void confirm()}>
                  {busy ? "Saving…" : preview.kind === "request" ? "Request the test" : "Postpone"}
                </Button>
              ))}
          </div>
        </div>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
