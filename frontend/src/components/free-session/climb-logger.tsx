"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { Zap, Check, X, Plus, Minus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GradePicker } from "./grade-picker";
import { RestTimer } from "./rest-timer";
import { logFreeClimb, deleteFreeClimb } from "@/lib/api";
import { displayBoulderGrade, type BoulderGradeSystem } from "@/lib/gradeUtils";
import {
  saveDraft,
  loadDraft,
  clearDraft,
  type FreeSessionDraft,
} from "@/lib/free-session-utils";

export interface LoggedClimb {
  index: number;
  grade: string;
  status: string;
  attempts: number;
  style?: string;
  topped?: boolean;
  notes?: string;
  logged_at: string;
}

interface ClimbLoggerProps {
  sessionId: string;
  surface: string;
  sessionMode: "template" | "free";
  presetName?: string;
  gymName?: string;
  targetGrade?: string;
  restSeconds?: number;
  tip?: string;
  targetClimbs?: string;
  onFinish: () => void;
  onCancel?: () => void;
  onClimbLogged?: (climb: LoggedClimb) => void;
  gradeSystem?: BoulderGradeSystem;
}

const isLead = (surface: string) => surface === "gym_routes";

export function ClimbLogger({
  sessionId,
  surface,
  sessionMode,
  presetName,
  gymName,
  targetGrade,
  restSeconds,
  tip,
  targetClimbs,
  onFinish,
  onCancel,
  onClimbLogged,
  gradeSystem = "font",
}: ClimbLoggerProps) {
  // Form state
  const [grade, setGrade] = useState(targetGrade || "6A");
  const [status, setStatus] = useState<"flash" | "sent" | "attempted">("flash");
  const [attempts, setAttempts] = useState(1);
  const [style, setStyle] = useState<string | undefined>(isLead(surface) ? "onsight" : undefined);
  const [topped, setTopped] = useState<boolean>(true);
  const [notes, setNotes] = useState("");
  const [showNotes, setShowNotes] = useState(false);

  // Session state
  const [climbs, setClimbs] = useState<LoggedClimb[]>([]);
  const [isLogging, setIsLogging] = useState(false);
  const [deletingIndex, setDeletingIndex] = useState<number | null>(null);
  const [restKey, setRestKey] = useState(0);
  const [showRest, setShowRest] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [resumed, setResumed] = useState(false);
  const startedAt = useRef(Date.now());
  const [elapsedSecs, setElapsedSecs] = useState(0);

  // Refs for history scroll (scroll to bottom on new climb)
  const historyRef = useRef<HTMLDivElement>(null);
  const draftSavedRef = useRef(false);

  // ── Restore draft on mount ──────────────────────────────────────────────
  useEffect(() => {
    const draft = loadDraft(sessionId);
    if (!draft) return;

    setGrade(draft.currentGrade);
    setStatus(draft.currentStatus);
    setAttempts(draft.currentAttempts);
    if (draft.currentStyle !== undefined) setStyle(draft.currentStyle);
    if (draft.currentTopped !== undefined) setTopped(draft.currentTopped);
    setNotes(draft.currentNotes);
    if (draft.loggedClimbs.length > 0) {
      setClimbs(draft.loggedClimbs);
      startedAt.current = draft.startedAt;
      setResumed(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // Hide resume banner after 4s
  useEffect(() => {
    if (!resumed) return;
    const id = setTimeout(() => setResumed(false), 4000);
    return () => clearTimeout(id);
  }, [resumed]);

  // ── Elapsed timer ──────────────────────────────────────────────────────
  useEffect(() => {
    const id = setInterval(() => {
      setElapsedSecs(Math.floor((Date.now() - startedAt.current) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const elapsedMin = Math.floor(elapsedSecs / 60);
  const elapsedSec = elapsedSecs % 60;

  // ── Auto-set attempts based on status ──────────────────────────────────
  useEffect(() => {
    if (status === "flash") setAttempts(1);
    else if (status === "sent" && attempts < 2) setAttempts(2);
    else if (status === "attempted" && attempts < 1) setAttempts(1);
  }, [status, attempts]);

  // ── Lead style → auto attempts ─────────────────────────────────────────
  useEffect(() => {
    if (isLead(surface)) {
      if (style === "onsight" || style === "flash") {
        setStatus("flash");
        setAttempts(1);
      } else if (style === "redpoint") {
        setStatus("sent");
        if (attempts < 2) setAttempts(2);
      } else if (style === "project") {
        setStatus("attempted");
      }
    }
  }, [style, surface, attempts]);

  // ── Draft persistence: save on every form state change ─────────────────
  useEffect(() => {
    // Skip the very first render before mount-restore completes
    if (!draftSavedRef.current && climbs.length === 0) {
      draftSavedRef.current = true;
      return;
    }
    draftSavedRef.current = true;

    const draft: FreeSessionDraft = {
      version: 1,
      sessionId,
      surface,
      sessionMode,
      presetName,
      gymName,
      targetGrade,
      restSeconds,
      tip,
      targetClimbs,
      currentGrade: grade,
      currentStatus: status,
      currentAttempts: attempts,
      currentStyle: style,
      currentTopped: topped,
      currentNotes: notes,
      loggedClimbs: climbs,
      startedAt: startedAt.current,
    };
    saveDraft(draft);
  }, [
    grade, status, attempts, style, topped, notes, climbs,
    sessionId, surface, sessionMode, presetName, gymName,
    targetGrade, restSeconds, tip, targetClimbs,
  ]);

  // ── beforeunload warning ───────────────────────────────────────────────
  useEffect(() => {
    function onBeforeUnload(e: BeforeUnloadEvent) {
      if (climbs.length > 0) {
        e.preventDefault();
        e.returnValue = "";
      }
    }
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [climbs.length]);

  // ── Handlers ───────────────────────────────────────────────────────────

  const handleLog = useCallback(async () => {
    if (isLogging) return;
    setIsLogging(true);
    try {
      const result = await logFreeClimb(sessionId, {
        grade,
        status,
        attempts,
        style: isLead(surface) ? style : undefined,
        topped: isLead(surface) ? topped : undefined,
        notes: notes || undefined,
      });

      const newClimb: LoggedClimb = {
        index: result.index,
        grade,
        status,
        attempts,
        style: isLead(surface) ? style : undefined,
        topped: isLead(surface) ? topped : undefined,
        notes: notes || undefined,
        logged_at: result.logged_at,
      };

      // Issue 3: append at bottom (chronological order)
      setClimbs((prev) => [...prev, newClimb]);
      onClimbLogged?.(newClimb);

      // Scroll history to bottom
      setTimeout(() => {
        historyRef.current?.scrollTo({ top: historyRef.current.scrollHeight, behavior: "smooth" });
      }, 50);

      // Reset form
      setStatus("flash");
      setNotes("");
      setShowNotes(false);
      if (isLead(surface)) {
        setStyle("onsight");
        setTopped(true);
      }

      // Start rest timer in template mode
      if (sessionMode === "template" && restSeconds) {
        setShowRest(true);
        setRestKey((k) => k + 1);
      }
    } catch (err) {
      console.error("Failed to log climb:", err);
    } finally {
      setIsLogging(false);
    }
  }, [sessionId, grade, status, attempts, style, topped, notes, surface, sessionMode, restSeconds, isLogging]);

  const handleDeleteClimb = useCallback(async (climbIndex: number) => {
    // Optimistic remove
    const removed = climbs.find((c) => c.index === climbIndex);
    if (!removed) return;
    setDeletingIndex(climbIndex);
    setClimbs((prev) => prev.filter((c) => c.index !== climbIndex));
    try {
      await deleteFreeClimb(sessionId, climbIndex);
    } catch {
      // Rollback on failure
      setClimbs((prev) => {
        const restored = [...prev, removed].sort((a, b) => a.index - b.index);
        return restored;
      });
    } finally {
      setDeletingIndex(null);
    }
  }, [sessionId, climbs]);

  const handleFinish = useCallback(() => {
    clearDraft(sessionId);
    onFinish();
  }, [sessionId, onFinish]);

  const handleCancel = useCallback(() => {
    clearDraft(sessionId);
    onCancel?.();
  }, [sessionId, onCancel]);

  const targetMax = targetClimbs ? parseInt(targetClimbs.split("-")[1] || "0") : 0;
  const statusIcons = {
    flash: <Zap className="size-4" />,
    sent: <Check className="size-4" />,
    attempted: <X className="size-4" />,
  };
  const statusColors = {
    flash: "bg-amber-500/20 text-amber-400 border-amber-500/40",
    sent: "bg-emerald-500/20 text-emerald-400 border-emerald-500/40",
    attempted: "bg-red-500/20 text-red-400 border-red-500/40",
  };

  return (
    <div className="flex flex-col gap-4 px-4 pb-32">
      {/* Header */}
      <div className="text-center">
        <h2 className="text-lg font-semibold">
          {presetName && <>{presetName} &middot; </>}
          {surface === "gym_boulder" ? "Gym Boulder" :
           surface === "board_kilter" ? "Kilter" :
           surface === "board_moonboard" ? "Moon" :
           surface === "board_other" ? "Board" :
           "Lead"}
          {gymName && <> &middot; {gymName}</>}
        </h2>
        {sessionMode === "template" && targetGrade && restSeconds && (
          <p className="text-sm text-muted-foreground">
            Target: ~{isLead(surface) ? targetGrade : displayBoulderGrade(targetGrade, gradeSystem)} &middot; Rest: {Math.floor(restSeconds / 60)}:{String(restSeconds % 60).padStart(2, "0")}
          </p>
        )}
      </div>

      {/* Resume banner */}
      {resumed && (
        <div className="flex items-center justify-between rounded-lg border border-primary/30 bg-primary/10 px-3 py-2 text-sm">
          <span className="text-primary font-medium">
            Session resumed — {climbs.length} {isLead(surface) ? "routes" : "boulders"} restored
          </span>
          <button onClick={() => setResumed(false)} className="ml-2 text-primary/60 hover:text-primary">
            <X className="size-3.5" />
          </button>
        </div>
      )}

      {/* Phase tip */}
      {tip && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3">
          <p className="text-sm text-amber-200">{tip}</p>
        </div>
      )}

      {/* LOG FORM */}
      <div className="rounded-xl border bg-card p-4">
        <div className="mb-4">
          <GradePicker value={grade} onChange={setGrade} gradeSystem={isLead(surface) ? "font" : gradeSystem} />
        </div>

        {/* Boulder status selector */}
        {!isLead(surface) && (
          <div className="mb-4 flex gap-2">
            {(["flash", "sent", "attempted"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setStatus(s)}
                className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg border px-3 py-2.5 text-sm font-medium transition-all ${
                  status === s ? statusColors[s] : "border-border text-muted-foreground hover:border-foreground/20"
                }`}
              >
                {statusIcons[s]}
                {s === "flash" ? "Flash" : s === "sent" ? "Sent" : "Tried"}
              </button>
            ))}
          </div>
        )}

        {/* Lead style selector */}
        {isLead(surface) && (
          <div className="mb-4 flex gap-2">
            {(["onsight", "flash", "redpoint", "project"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setStyle(s)}
                className={`flex-1 rounded-lg border px-2 py-2.5 text-xs font-medium transition-all ${
                  style === s
                    ? "border-primary/50 bg-primary/20 text-primary"
                    : "border-border text-muted-foreground hover:border-foreground/20"
                }`}
              >
                {s === "onsight" ? "OS" : s === "flash" ? "FL" : s === "redpoint" ? "RP" : "PROJ"}
              </button>
            ))}
          </div>
        )}

        {/* Lead topped toggle */}
        {isLead(surface) && (
          <div className="mb-4 flex gap-2">
            <button
              onClick={() => setTopped(true)}
              className={`flex-1 rounded-lg border py-2 text-sm font-medium transition-all ${
                topped
                  ? "border-emerald-500/50 bg-emerald-500/20 text-emerald-400"
                  : "border-border text-muted-foreground"
              }`}
            >
              Topped
            </button>
            <button
              onClick={() => setTopped(false)}
              className={`flex-1 rounded-lg border py-2 text-sm font-medium transition-all ${
                !topped
                  ? "border-red-500/50 bg-red-500/20 text-red-400"
                  : "border-border text-muted-foreground"
              }`}
            >
              Fell
            </button>
          </div>
        )}

        {/* Attempts picker — Issue 4: better label */}
        {(((!isLead(surface) && status !== "flash") ||
          (isLead(surface) && (style === "redpoint" || style === "project"))) && (
          <div className="mb-4">
            <p className="mb-2 text-center text-xs text-muted-foreground">
              {status === "sent" ? `${attempts} attempt${attempts !== 1 ? "s" : ""} to send` : `${attempts} attempt${attempts !== 1 ? "s" : ""} — didn't send`}
            </p>
            <div className="flex items-center justify-center gap-4">
              <Button
                variant="outline"
                size="icon-sm"
                onClick={() => setAttempts(Math.max(status === "sent" ? 2 : 1, attempts - 1))}
              >
                <Minus className="size-4" />
              </Button>
              <span className="min-w-[32px] text-center text-xl font-bold tabular-nums">{attempts}</span>
              <Button
                variant="outline"
                size="icon-sm"
                onClick={() => setAttempts(Math.min(20, attempts + 1))}
              >
                <Plus className="size-4" />
              </Button>
            </div>
          </div>
        ))}

        {/* Notes toggle */}
        {!showNotes ? (
          <button
            onClick={() => setShowNotes(true)}
            className="mb-3 text-xs text-muted-foreground hover:text-foreground"
          >
            + Add note
          </button>
        ) : (
          <input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add a note..."
            className="mb-3 w-full rounded-lg border bg-transparent px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus:border-primary/50"
          />
        )}

        {/* LOG button */}
        <Button
          onClick={handleLog}
          disabled={isLogging}
          className="w-full text-base font-semibold"
          size="lg"
        >
          {isLogging ? "Logging..." : isLead(surface) ? "Log Route" : "Log Boulder"}
        </Button>
      </div>

      {/* Rest timer */}
      {sessionMode === "template" && restSeconds && showRest ? (
        <RestTimer
          key={restKey}
          initialSeconds={restSeconds}
          autoStart={true}
          onComplete={() => setShowRest(false)}
        />
      ) : sessionMode === "free" ? (
        <RestTimer initialSeconds={180} autoStart={false} />
      ) : null}

      {/* Climb history — Issue 1: scrollable container, Issue 3: chronological (append order), Issue 5: delete button */}
      {climbs.length > 0 && (
        <div className="rounded-xl border bg-card p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium text-muted-foreground">Logged</span>
            <span className="text-sm text-muted-foreground">
              {climbs.length}{targetMax > 0 ? `/${targetMax}` : ""} {isLead(surface) ? "routes" : "boulders"}
            </span>
          </div>
          {/* Issue 1: max-height + scroll */}
          <div ref={historyRef} className="flex max-h-[240px] flex-col gap-1.5 overflow-y-auto">
            {climbs.map((c) => (
              <div key={c.index} className="group flex items-center gap-2 text-sm">
                <span className="w-6 shrink-0 text-right text-xs text-muted-foreground">#{c.index}</span>
                <span className="font-medium">{isLead(surface) ? c.grade : displayBoulderGrade(c.grade, gradeSystem)}</span>
                <span className={`flex shrink-0 items-center gap-0.5 ${
                  c.status === "flash" ? "text-amber-400" :
                  c.status === "sent" ? "text-emerald-400" : "text-red-400"
                }`}>
                  {statusIcons[c.status as keyof typeof statusIcons]}
                  {c.status}
                  {c.status !== "flash" && <span className="text-muted-foreground">({c.attempts})</span>}
                </span>
                {isLead(surface) && c.style && (
                  <span className="text-xs text-muted-foreground uppercase">{c.style}</span>
                )}
                {c.notes && <span className="min-w-0 truncate text-xs text-muted-foreground">{c.notes}</span>}
                {/* Issue 5: delete button */}
                <button
                  onClick={() => handleDeleteClimb(c.index)}
                  disabled={deletingIndex === c.index}
                  className="ml-auto shrink-0 text-muted-foreground/40 opacity-0 transition-opacity hover:text-red-400 group-hover:opacity-100 disabled:opacity-50"
                  aria-label={`Delete climb #${c.index}`}
                >
                  <Trash2 className="size-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer stats */}
      <div className="flex items-center justify-between rounded-xl border bg-card px-4 py-3">
        <span className="text-sm font-medium">
          {isLead(surface) ? "Routes" : "Boulders"}: {climbs.length}
          {targetMax > 0 && <span className="text-muted-foreground">/{targetMax}</span>}
        </span>
        <span className="text-lg font-bold tabular-nums">
          {elapsedMin}:{String(elapsedSec).padStart(2, "0")}
        </span>
      </div>

      {/* Finish / Cancel buttons */}
      {!showConfirm && !showCancelConfirm && (
        <div className="flex gap-2">
          <Button
            variant="ghost"
            onClick={() => setShowCancelConfirm(true)}
            className="text-muted-foreground"
          >
            Cancel
          </Button>
          <Button
            variant="outline"
            onClick={() => setShowConfirm(true)}
            className="flex-1"
          >
            Finish Session
          </Button>
        </div>
      )}

      {/* Finish confirmation */}
      {showConfirm && (
        <div className="rounded-xl border bg-card p-4">
          <p className="mb-3 text-center text-sm">
            Finish session? You logged {climbs.length} {isLead(surface) ? "routes" : "boulders"}.
          </p>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowConfirm(false)} className="flex-1">
              Keep climbing
            </Button>
            <Button onClick={handleFinish} className="flex-1">
              Finish
            </Button>
          </div>
        </div>
      )}

      {/* Cancel confirmation */}
      {showCancelConfirm && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4">
          <p className="mb-3 text-center text-sm">
            Cancel this session?{climbs.length > 0 && ` All ${climbs.length} logged ${isLead(surface) ? "routes" : "boulders"} will be lost.`}
          </p>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowCancelConfirm(false)} className="flex-1">
              Keep climbing
            </Button>
            <Button variant="destructive" onClick={handleCancel} className="flex-1">
              Cancel session
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
