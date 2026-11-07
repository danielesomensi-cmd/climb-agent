"use client";

import { useCallback, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { apiErrorDetail } from "@/lib/api";
import {
  announcePendingSync,
  clearOrphan,
  syncPendingGuidedFeedback,
} from "@/lib/guided-pending-feedback";
import {
  OrphanPlacementError,
  loadDayFromServer,
  orphanOptions,
  placeOrphanSession,
  sessionLabel,
  type DayOnServer,
  type OrphanPlacement,
} from "@/lib/orphan-session";
import { useSubmitLock } from "@/lib/hooks/use-submit-lock";

/**
 * B414 (INBOX-2026-11-04-ORPHAN) — the player's box for a session the server
 * refused because it is no longer on that day of the plan. Nothing was saved;
 * the feedback stays on the phone until the athlete picks:
 *  - «Log it in place of X» (one per session of the day still to do),
 *  - «Log it as an extra» (only when the day has a free slot),
 *  - «Discard» (asks first).
 * Errors are always shown: the box never pretends something was saved.
 */
export interface OrphanSessionBoxProps {
  date: string;
  sessionId: string;
  sessionName: string;
  /** The localStorage key of the saved session (the player pinned it). */
  storageKey: string;
  /** Placed and sent (or queued again), or discarded: leave the player. */
  onDone: () => void;
}

type Load = { state: "loading" } | { state: "offline" } | { state: "error"; message: string } | { state: "ready"; where: DayOnServer };

export function OrphanSessionBox({ date, sessionId, sessionName, storageKey, onDone }: OrphanSessionBoxProps) {
  const qc = useQueryClient();
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [error, setError] = useState<string | null>(null);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [queued, setQueued] = useState(false);

  const fetchDay = useCallback(async () => {
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      setLoad({ state: "offline" });
      return;
    }
    setLoad({ state: "loading" });
    try {
      const where = await loadDayFromServer(qc, date);
      if (!where) {
        setLoad({ state: "error", message: "That day is no longer in your plan." });
        return;
      }
      setLoad({ state: "ready", where });
    } catch (err) {
      setLoad({ state: "error", message: apiErrorDetail(err, "Couldn't load your plan. Check your connection.") });
    }
  }, [qc, date]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchDay();
  }, [fetchDay]);

  /** The session is on the day: send the saved feedback through the replay. */
  const sendSaved = useCallback(async () => {
    setError(null);
    clearOrphan(storageKey);
    try {
      announcePendingSync(await syncPendingGuidedFeedback(qc));
    } catch (err) {
      console.error("[guided] orphan feedback sync failed:", err);
    }
    let raw: string | null = "";
    try {
      raw = window.localStorage.getItem(storageKey);
    } catch {
      raw = "";
    }
    if (raw === null) {
      onDone();
      return;
    }
    let refusedAgain = false;
    try {
      refusedAgain = !!(raw && (JSON.parse(raw) as { orphan?: unknown }).orphan);
    } catch {
      refusedAgain = false;
    }
    if (refusedAgain) {
      // The server still does not see it on that day: nothing was saved.
      setError("Your plan still doesn't have this session on that day — nothing was saved.");
      void fetchDay();
      return;
    }
    // In the plan, not sent yet (connection): the replay sends it later.
    setQueued(true);
  }, [qc, storageKey, onDone, fetchDay]);

  const place = useCallback(
    async (where: DayOnServer, placement: OrphanPlacement) => {
      setError(null);
      try {
        await placeOrphanSession(qc, where, date, sessionId, placement);
      } catch (err) {
        setError(
          err instanceof OrphanPlacementError
            ? err.message
            : apiErrorDetail(err, "Couldn't update your plan — nothing was changed."),
        );
        return;
      }
      await sendSaved();
    },
    [qc, date, sessionId, sendSaved],
  );
  const { run: runPlace, busy: placing } = useSubmitLock(place);
  const { run: runSend, busy: sending } = useSubmitLock(sendSaved);

  const discard = useCallback(() => {
    try {
      window.localStorage.removeItem(storageKey);
    } catch {
      setError("Couldn't remove it from this device.");
      return;
    }
    onDone();
  }, [storageKey, onDone]);

  const busy = placing || sending;
  const day = load.state === "ready" ? load.where.day : null;
  const backInPlan = !!day?.sessions?.some(
    (s) => s.session_id === sessionId && s.status !== "done" && s.status !== "skipped",
  );
  const options = orphanOptions(day, sessionId);

  return (
    <Card className="gap-0 py-0 border-warning/40">
      <CardContent className="space-y-4 py-5">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 size-5 shrink-0 text-warning" />
          <div className="space-y-1">
            <p className="font-medium">This session is no longer in your plan</p>
            <p className="text-sm text-muted-foreground">
              {sessionName} was removed or replaced on that day while you trained. Nothing was saved yet — your
              feedback is kept on this device until you choose.
            </p>
          </div>
        </div>

        {load.state === "loading" && <p className="text-sm text-muted-foreground">Checking your plan…</p>}
        {load.state === "offline" && (
          <p className="text-sm text-warning">You&apos;re offline — connect to choose what to do.</p>
        )}
        {load.state === "error" && <p className="text-sm text-warning">{load.message}</p>}
        {queued && (
          <p className="text-sm text-muted-foreground">
            It&apos;s in your plan now; the feedback is sent as soon as the connection is back.
          </p>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}

        {load.state === "ready" && !queued && (
          <div className="space-y-2">
            {backInPlan ? (
              <>
                <p className="text-sm">It is back in your plan for that day.</p>
                <Button className="min-h-[44px] w-full" disabled={busy} onClick={() => void runSend()}>
                  {sending ? "Sending..." : "Send it now"}
                </Button>
              </>
            ) : (
              <>
                {day && day.sessions && day.sessions.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    Now on that day: {day.sessions.map((s) => sessionLabel(s)).join(", ")}
                  </p>
                )}
                {options.placeable &&
                  options.replace.map((target) => (
                    <Button
                      key={`${target.session_id}-${target.slot}`}
                      className="min-h-[44px] w-full justify-start whitespace-normal text-left"
                      disabled={busy}
                      onClick={() => void runPlace(load.where, { kind: "replace", target })}
                    >
                      Log it in place of {sessionLabel(target)}
                    </Button>
                  ))}
                {options.placeable && options.extraSlot && (
                  <Button
                    variant="secondary"
                    className="min-h-[44px] w-full"
                    disabled={busy}
                    onClick={() => void runPlace(load.where, { kind: "extra", slot: options.extraSlot! })}
                  >
                    Log it as an extra ({options.extraSlot})
                  </Button>
                )}
                {!options.placeable && (
                  <p className="text-xs text-muted-foreground">
                    A generated session can&apos;t be put back from here: ask the coach, or discard it.
                  </p>
                )}
              </>
            )}
          </div>
        )}

        {(load.state === "offline" || load.state === "error") && (
          <Button variant="outline" className="min-h-[44px] w-full" disabled={busy} onClick={() => void fetchDay()}>
            Try again
          </Button>
        )}

        {!queued &&
          (confirmDiscard ? (
            <div className="space-y-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3">
              <p className="text-sm">Discard this session? Its feedback is deleted and can&apos;t be recovered.</p>
              <div className="flex gap-2">
                <Button variant="outline" className="min-h-[44px] flex-1" onClick={() => setConfirmDiscard(false)}>
                  Keep it
                </Button>
                <Button variant="destructive" className="min-h-[44px] flex-1" onClick={discard}>
                  Discard
                </Button>
              </div>
            </div>
          ) : (
            <Button
              variant="ghost"
              className="min-h-[44px] w-full text-muted-foreground"
              disabled={busy}
              onClick={() => setConfirmDiscard(true)}
            >
              Discard
            </Button>
          ))}
      </CardContent>
    </Card>
  );
}
